import datetime
import locale as localelib
import re
import time
from urlparse import urljoin

from scrapy import log
from scrapy.contrib.loader.processor import Compose, MapCompose, TakeFirst
from scrapy.utils.markup import (remove_tags, replace_escape_chars,
                                 unquote_markup)


_clean_spaces_re = re.compile("\s+", re.U)
def clean_spaces(value):
    return _clean_spaces_re.sub(' ', value)


def make_absolute_url(val, loader_context):
    base_url = loader_context.get('base_url')
    if base_url is None:
        response = loader_context.get('response')
        if response is None:
            raise AttributeError('You must provide a base_url or a response '
                                 'to the loader context')
        base_url = response.url
    return urljoin(base_url, val)


def remove_query_params(value):
    # some urls don't have ? but have &
    return value.split('?')[0].split('&')[0]


_br_re = re.compile('<br\s?\/?>', re.IGNORECASE)
def replace_br(value):
    return _br_re.sub(' ', value)


def replace_escape(value):
    return replace_escape_chars(value, replace_by=u' ')


def split(value):
    return [v.strip() for v in value.split(',')]


def strip(value):
    return value.strip()


def to_datetime(value, format, locale=None):
    """Returns a datetime parsed from value with the specified format
    and locale.

    If no year is specified in the parsing format it is taken from the
    current date.
    """
    if locale:
        old_locale = localelib.getlocale(localelib.LC_ALL)
        localelib.setlocale(localelib.LC_ALL, locale)

    time_s = time.strptime(value, format)
    dt = datetime.datetime(*time_s[0:5])
    # 1900 is the default year from strptime, means no year parsed
    if dt.year == 1900:
        dt = dt.replace(year=datetime.datetime.utcnow().year)

    if locale:
        localelib.setlocale(localelib.LC_ALL, old_locale)

    return dt


def to_date(value, format, locale=None):
    return to_datetime(value, format, locale).date()


def to_time(value, format):
    time_s = time.strptime(value, format)
    return datetime.time(time_s[3], time_s[4])


# defaults

default_input_processor = MapCompose(unquote_markup, replace_br, remove_tags,
                                     replace_escape, strip, clean_spaces)

default_output_processor = TakeFirst()
