#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import logging
import os
import os.path
import pytz
import sys
from ConfigParser import SafeConfigParser
from datetime import datetime
from dateutil import parser

import pinboard
from jinja2 import Environment, PackageLoader
from slugify import Slugify
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
    global log
    args = parse_args()

    # create logger
    if args.verbosity >=2:
        logging_level = logging.INFO
    elif args.verbosity == 1:
        logging_level = logging.WARNING
    else:
        logging_level = logging.NOTSET

    logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s',
                          datefmt='%H:%M:%S',
                          stream=sys.stdout,
                          level=logging_level)

    log = logging.getLogger(__name__)


    # check output path can be written to
    if not os.access(args.output, os.W_OK):
        log.error("Can not write to '{0}'.".format(args.output))
        sys.exit()

    # load config
    config = load_config()
    if config is False:
        log.error("Could not open config.ini, quitting")
        sys.exit()

    # load stopwords
    stopwords = []
    try:
        for line in args.stopwords:
            stopwords.append(line.strip())
        log.debug("Loaded stopwords from '{0}'".format(args.stopwords.name))
    except Exception as e:
        log.warning("Could not load stopwords from '{0}': {1}".format(args.stopwords, e.message))
    log.debug("{0} stopwords loaded.".format(len(stopwords)))

    # load template
    jinja_env = Environment(loader=PackageLoader('pindown', '.'),
                            trim_blocks=True,
                            lstrip_blocks=True)
    try:
        template = jinja_env.get_template(args.template.name)
        log.debug("Loaded template '{0}'".format(args.template.name))
    except Exception as e:
        log.warning("Could not load custom template '{0}', using default".format(e.message))
        template = jinja_env.from_string("Title: {{ description }}\n"
                                         "Category: linklist\n"
                                         "Link: {{ url }}\n"
                                         "Date: {{ date }}\n"
                                         "Tags: {{ tags|join(', ') }}\n"
                                         "Status: draft\n"
                                         "\n"
                                         "{{ extended }}\n")

    # prepare timezones
    if args.timezone is not None:
        try:
            local_tz = pytz.timezone(args.timezone)
        except Exception as e:
            log.error("Could not assign custom timezone ({0})".format(e.message))
    else:
        local_tz = pytz.timezone(config['local_tz'])
    utc_tz = pytz.UTC
    log.info("Local timezone: {0}".format(local_tz))

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
        log.info("No update necessary.")
        sys.exit()
    else:
        # update
        pins = pb.posts.all(fromdt=last_import)
        log.info("New pins: {0}".format(len(pins)))

        for pin in pins:
            # create filename from slug
            custom_slug_builder = Slugify(to_lower=True, max_length=32, stop_words=stopwords)
            slug = custom_slug_builder(pin.description)
            write_path = os.path.join(args.output, slug + ".md")

            # build a context for jinja
            context = { 'description': pin.description,
                        'url': pin.url,
                        'time': pin.time.replace(tzinfo=utc_tz),
                        'tags': pin.tags,
                        'extended': pin.extended,
                        'hash': pin.hash,
                        'meta': pin.meta,
                        'shared': pin.shared,
                        'toread': pin.toread,
                        # for convenience
                        'date': pin.time.replace(tzinfo=utc_tz).astimezone(local_tz).isoformat() }

            # render template
            try:
                output = template.render(context)
            except Exception as e:
                log.error("Could not write '{0}.md': {1}".format(slug, e))
                continue

            # write output
            if args.debug is not True:
                if not os.path.isfile(write_path):
                    with open(write_path, 'w') as f:
                        f.write(output)
                    log.info("Wrote '{0}'".format(write_path))
                else:
                    log.info("Skipped '{0}' (already exists)".format(write_path))
            else:
                log.info("Skipped '{0}' (debug mode)".format(write_path))

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
        log.debug("Config loaded")
        return config
    except Exception as e:
        log.error(e.message)
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
        log.error("Could not save config: " + e.message)
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


if __name__ == "__main__":
    main()
