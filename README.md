# Pindown

Create text files for static site generators from Pinboard.in bookmarks.

## Installation

A sample config.ini file is included. There are three options:

### local_tz

Which timezone you want to use for posts. Pindown uses timezones from the [Olson database](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

### pinboard_api_token

You will need to add your own Pinboard API token. This can be found [here](https://pinboard.in/settings/password). 

### last_import

This will get updated each time the script is run so that only the most recent bookmarks will be used.

## Usage

Run the script manually, or set up a cronjob to run it regularly. 

## History

### 2015-11-18:

+ Removed custom timestamp class.
+ Script now defaults to using external templates and stopword lists. Hardcoded defaults in case of error.

### 2015-11-17:

+ Added debug mode (-d) to disable output.
+ Added support for optional Jinja2 templates (-t). Default template is still hard-coded.
+ Added support for custom local timezones (-z).
+ Added support for custom stopwords file (-s).
+ Switched to a slightly less temperamental INI config file instead of JSON.
+ Moved default stopwords out of config file.
+ Trimmed most cruft from the config file.
+ Added ugly unicode hack. Not happy.
+ Tried to make the code a little more readable.


## Credits

Written by Dave Raftery. Mostly a learning exercise.

## License

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.