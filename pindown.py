#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import os.path
import pytz
import sys
import argparse
from ConfigParser import SafeConfigParser
from datetime import datetime
from dateutil import parser

import pinboard
from slugify import Slugify
from jinja2 import Environment, PackageLoader
from tzlocal import get_localzone

LOG_NOTICE = 2
LOG_WARNING = 2
LOG_ERROR = 1
LOG_OUTPUT = 1

# filthy unicode hack
reload(sys)
sys.setdefaultencoding('utf-8')

def main():
    # parse arguments
    global args
    args = parse_args()

    # check output path can be written to
    if not os.access(args.output, os.W_OK):
        log("Can not write to '{0}'.".format(args.output))
        sys.exit()

    # load config
    config = load_config()
    if config is False:
        log("Could not open config.ini, quitting")
        sys.exit()

    # load stopwords
    stopwords = []
    try:
        for line in args.stopwords:
            stopwords.append(line.strip())
        log("Loaded stopwords from '{0}'".format(args.stopwords.name), level=LOG_NOTICE)
    except Exception as e:
        log("Could not load stopwords from '{0}': {1}".format(args.stopwords, e.message), level=LOG_ERROR)
        stopwords.extend(get_default_stopwords())
    log("{0} stopwords loaded.".format(len(stopwords), level=LOG_NOTICE))
    
    # load template
    jinja_env = Environment(loader=PackageLoader('pindown', '.'))
    try:
        template = jinja_env.get_template(args.template.name)
        log("Loaded template '{0}'".format(args.template.name), level=LOG_NOTICE)
    except Exception as e:
        log("Could not load custom template '{0}', using default".format(e.message), level=LOG_ERROR)
        template = jinja_env.from_string("Title: {{ title }}\n"
                                         "Category: linklist\n"
                                         "Link: {{ link }}\n"
                                         "Date: {{ date }}\n"
                                         "Tags: {{ tags }}\n"
                                         "Status: draft\n"
                                         "\n"
                                         "{{ contents }}\n")
    
    # prepare timezones
    if args.timezone is not None:
        try:
            local_tz = pytz.timezone(args.timezone)
        except Exception as e:
            log("Could not assign custom timezone ({0})".format(e.message), level=LOG_ERROR)
    else:
        local_tz = pytz.timezone(config['local_tz'])
    utc_tz = pytz.UTC
    log("Local timezone: {0}".format(local_tz), level=LOG_NOTICE)
    
    # connect to api
    pb = pinboard.Pinboard(config['pinboard_api_token'])
    
    # grab last updated date from api, compare to late updated date in config
    # all dates from pinboard are in UTC, just make this explicit
    last_update = pb.posts.update().replace(tzinfo=utc_tz)
    if 'last_import' in config.keys() and config['last_import'] is not None:
        last_import = parser.parse(config['last_import'])
    else:
        last_import = datetime.utcnow().replace(tzinfo=utc_tz)
        config['last_import'] = last_import
    
    if last_update <= last_import:
        # no update
        log("No update necessary.", level=LOG_NOTICE)
        sys.exit()
    else:
        # update
        pins = pb.posts.all(fromdt=last_import)
        log("New pins: {0}".format(len(pins)))
        
        for pin in pins:
            # create filename from slug
            custom_slug_builder = Slugify(to_lower=True, max_length=32, stop_words=stopwords)
            slug = custom_slug_builder(pin.description)
            write_path = os.path.join(args.output, slug + ".md")
            
            # place the description in MD blockquotes
            contents = u""
            for para in pin.extended.encode('utf-8').split('\n'):
                contents += u"> {0}\n".format(para.strip())
            
            # build a context for jinja
            context = { 'title': pin.description.encode('utf-8'),
                        'link': pin.url,
                        'date': pin.time.replace(tzinfo=utc_tz).astimezone(local_tz).isoformat(),
                        'tags': ", ".join(pin.tags),
                        'contents': contents }
            
            # render template
            try:
                output = template.render(context)
            except Exception as e:
                log("Could not write '{0}.md': {1}".format(slug, e), level=LOG_ERROR)
                continue
            
            # write output
            if args.debug is not True:
                if not os.path.isfile(write_path):
                    with open(write_path, 'w') as f:
                        f.write(output)
                    log("Wrote '{0}'".format(write_path), level=LOG_OUTPUT)
                else:
                    log("Skipped '{0}' (already exists)".format(write_path), level=LOG_OUTPUT)
            else:
                log("Skipped '{0}' (debug mode)".format(write_path), level=LOG_OUTPUT)
        
        # write config and quit
        if args.debug is not True: 
            config['last_import'] = last_update.isoformat()
            save_config(config)



def load_config():
    try:
        parser = SafeConfigParser()
        parser.read('config.ini')
        items = parser.items('pindown')
        config = {}
        for item in items:
            config[item[0]] = item[1]
        log("Config loaded", level=LOG_NOTICE)
        return config
    except Exception as e:
        log(e.message, level=LOG_ERROR)
        return False

def save_config(config):
    try:
        parser = SafeConfigParser()
        parser.add_section('pindown')
        for key, value in config.iteritems():
            parser.set('pindown', key, str(value))
        with open('config.ini', 'w') as f:
            parser.write(f)
        return True
    except Exception as e:
        log("Could not save config: " + e.message, level=LOG_ERROR)
        return False
    
def parse_args():
    ap = argparse.ArgumentParser(prog="Pindown", description="Script to pull down recent bookmarks from Pinboard.in and write them to a Markdown-formatted text file suitable for Pelican.")
    ap.add_argument('-d',
                    '--debug',
                    action='store_true',
                    help="debug mode: don't write any files")
    ap.add_argument('-v',
                    '--verbosity',
                    action="count",
                    help="verbosity level")
    ap.add_argument('-s',
                    '--stopwords',
                    default='stopwords.txt',
                    type=argparse.FileType('r'),
                    help="path to text file with stopwords")
    ap.add_argument('-t',
                    '--template',
                    default='template.md',
                    type=argparse.FileType('r'),
                    help="Jinja2 template for output files")
    ap.add_argument('-z',
                    '--timezone',
                    help="Olson-style timezone (e.g. Australia/Adelaide)")
    ap.add_argument('--version',
                    help="version information",
                    action="version",
                    version="%(prog)s 0.1")
                    
    ap.add_argument('output',
                    help="path to write Markdown-formatted text files")
    return ap.parse_args()

def log(message, show_ts=True, level=1):
    if (args.verbosity is not None and args.verbosity >= level) or args.debug is True:
        dt = datetime.utcnow().replace(tzinfo=pytz.UTC)
        if show_ts == True:
            try:
                tz = pytz.timezone(config['local_tz'])
            except:
                tz = pytz.UTC
            ts = dt.astimezone(tz).strftime("%H:%M")
            print("[{0}] {1}".format(ts, message))
        else:
            print(message)
    
def get_default_stopwords():
    return ["a", "ii", "about", "above", "according", "across", "39", "actually", "ad", 
            "adj", "ae", "af", "after", "afterwards", "ag", "again", "against", "ai", 
            "al", "all", "almost", "alone", "along", "already", "also", "although", 
            "always", "am", "among", "amongst", "an", "and", "another", "any", "anyhow", 
            "anyone", "anything", "anywhere", "ao", "aq", "ar", "are", "aren", "aren't", 
            "around", "arpa", "as", "at", "au", "aw", "az", "b", "ba", "bb", "bd", "be", 
            "became", "because", "become", "becomes", "becoming", "been", "before", 
            "beforehand", "begin", "beginning", "behind", "being", "below", "beside", 
            "besides", "between", "beyond", "bf", "bg", "bh", "bi", "billion", "bj", "bm", 
            "bn", "bo", "both", "br", "bs", "bt", "but", "buy", "bv", "bw", "by", "bz", 
            "c", "ca", "can", "can't", "cannot", "caption", "cc", "cd", "cf", "cg", "ch", 
            "ci", "ck", "cl", "click", "cm", "cn", "co", "co.", "com", "copy", "could", 
            "couldn", "couldn't", "cr", "cs", "cu", "cv", "cx", "cy", "cz", "d", "de", 
            "did", "didn", "didn't", "dj", "dk", "dm", "do", "does", "doesn", "doesn't", 
            "don", "don't", "down", "during", "dz", "e", "each", "ec", "edu", "ee", "eg", 
            "eh", "eight", "eighty", "either", "else", "elsewhere", "en", "end", "ending", 
            "enough", "er", "es", "et", "etc", "even", "ever", "every", "everyone", 
            "everything", "everywhere", "except", "f", "few", "fi", "fifty", "find", 
            "first", "five", "fj", "fk", "fm", "fo", "for", "former", "formerly", "forty", 
            "found", "four", "fr", "free", "from", "further", "fx", "g", "ga", "gb", "gd", 
            "ge", "get", "gf", "gg", "gh", "gi", "gl", "gm", "gmt", "gn", "go", "gov", 
            "gp", "gq", "gr", "gs", "gt", "gu", "gw", "gy", "h", "had", "has", "hasn", 
            "hasn't", "have", "haven", "haven't", "he", "he'd", "he'll", "he's", "help", 
            "hence", "her", "here", "here's", "hereafter", "hereby", "herein", "hereupon", 
            "hers", "herself", "him", "himself", "his", "hk", "hm", "hn", "home", 
            "homepage", "how", "however", "hr", "ht", "htm", "html", "http", "hu", 
            "hundred", "i", "i'd", "i'll", "i'm", "i've", "i.e.", "id", "ie", "if", "il", 
            "im", "in", "inc", "inc.", "indeed", "information", "instead", "int", "into", 
            "io", "iq", "ir", "is", "isn", "isn't", "it", "it's", "its", "itself", "j", 
            "je", "jm", "jo", "join", "jp", "k", "ke", "kg", "kh", "ki", "km", "kn", "kp", 
            "kr", "kw", "ky", "kz", "l", "la", "last", "later", "latter", "lb", "lc", 
            "least", "less", "let", "let's", "li", "like", "likely", "lk", "ll", "lr", 
            "ls", "lt", "ltd", "lu", "lv", "ly", "m", "ma", "made", "make", "makes", 
            "many", "maybe", "mc", "md", "me", "meantime", "meanwhile", "mg", "mh", 
            "microsoft", "might", "mil", "million", "miss", "mk", "ml", "mm", "mn", "mo", 
            "more", "moreover", "most", "mostly", "mp", "mq", "mr", "mrs", "ms", "msie", 
            "mt", "mu", "much", "must", "mv", "mw", "mx", "my", "myself", "mz", "n", "na", 
            "namely", "nc", "ne", "neither", "net", "netscape", "never", "nevertheless", 
            "new", "next", "nf", "ng", "ni", "nine", "ninety", "nl", "no", "nobody", 
            "none", "nonetheless", "noone", "nor", "not", "nothing", "now", "nowhere", 
            "np", "nr", "nu", "nz", "o", "of", "off", "often", "om", "on", "once", "one", 
            "one's", "only", "onto", "or", "org", "other", "others", "otherwise", "our", 
            "ours", "ourselves", "out", "over", "overall", "own", "p", "pa", "page", "pe", 
            "per", "perhaps", "pf", "pg", "ph", "pk", "pl", "pm", "pn", "pr", "pt", "pw", 
            "py", "q", "qa", "r", "rather", "re", "recent", "recently", "reserved", 
            "ring", "ro", "ru", "rw", "s", "sa", "same", "sb", "sc", "sd", "se", "seem", 
            "seemed", "seeming", "seems", "seven", "seventy", "several", "sg", "sh", 
            "she", "she'd", "she'll", "she's", "should", "shouldn", "shouldn't", "si", 
            "since", "site", "six", "sixty", "sj", "sk", "sl", "sm", "sn", "so", "some", 
            "somehow", "someone", "something", "sometime", "sometimes", "somewhere", "sr", 
            "st", "still", "stop", "su", "such", "sv", "sy", "sz", "t", "taking", "tc", 
            "td", "ten", "text", "tf", "tg", "test", "th", "than", "that", "that'll", 
            "that's", "the", "their", "them", "themselves", "then", "thence", "there", 
            "there'll", "there's", "thereafter", "thereby", "therefore", "therein", 
            "thereupon", "these", "they", "they'd", "they'll", "they're", "they've", 
            "thirty", "this", "those", "though", "thousand", "three", "through", 
            "throughout", "thru", "thus", "tj", "tk", "tm", "tn", "to", "together", "too", 
            "toward", "towards", "tp", "tr", "trillion", "tt", "tv", "tw", "twenty", 
            "two", "tz", "u", "ua", "ug", "uk", "um", "under", "unless", "unlike", 
            "unlikely", "until", "up", "upon", "us", "use", "used", "using", "uy", "uz", 
            "v", "va", "vc", "ve", "very", "vg", "vi", "via", "vn", "vu", "w", "was", 
            "wasn", "wasn't", "we", "we'd", "we'll", "we're", "we've", "web", "webpage", 
            "website", "welcome", "well", "were", "weren", "weren't", "wf", "what", 
            "what'll", "what's", "whatever", "when", "whence", "whenever", "where", 
            "whereafter", "whereas", "whereby", "wherein", "whereupon", "wherever", 
            "whether", "which", "while", "whither", "who", "who'd", "who'll", "who's", 
            "whoever", "NULL", "whole", "whom", "whomever", "whose", "why", "will", 
            "with", "within", "without", "won", "won't", "would", "wouldn", "wouldn't", 
            "ws", "www", "x", "y", "ye", "yes", "yet", "you", "you'd", "you'll", "you're", 
            "you've", "your", "yours", "yourself", "yourselves", "yt", "yu", "z", "za", 
            "zm", "zr", "10", "z", "org", "inc", "width", "length"]



if __name__ == "__main__":
    main()