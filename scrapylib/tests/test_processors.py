#!/usr/bin/env python
import datetime
import locale
import unittest

from scrapylib.processors import to_datetime, to_date


class TestProcessors(unittest.TestCase):

    def test_to_datetime(self):
        self.assertEquals(to_datetime('March 4, 2011 20:00', '%B %d, %Y %H:%S'),
                          datetime.datetime(2011, 3, 4, 20, 0))

        # test no year in parse format
        test_date = to_datetime('March 4, 20:00', '%B %d, %H:%S')
        self.assertEquals(test_date.year, datetime.datetime.utcnow().year)

        # test parse only date
        self.assertEquals(to_datetime('March 4, 2011', '%B %d, %Y'),
                          datetime.datetime(2011, 3, 4))

    def test_localized_to_datetime(self):
        current_locale = locale.getlocale(locale.LC_ALL)

        self.assertEquals(
            to_datetime('11 janvier 2011', '%d %B %Y', locale='fr_FR.UTF-8'),
            datetime.datetime(2011, 1, 11)
        )

        self.assertEquals(current_locale, locale.getlocale(locale.LC_ALL))

    def test_to_date(self):
        self.assertEquals(to_date('March 4, 2011', '%B %d, %Y'),
                          datetime.date(2011, 3, 4))

        # test no year in parse format
        test_date = to_date('March 4', '%B %d')
        self.assertEquals(test_date.year, datetime.datetime.utcnow().year)

    def test_localized_to_date(self):
        current_locale = locale.getlocale(locale.LC_ALL)

        self.assertEquals(
            to_date('11 janvier 2011', '%d %B %Y', locale='fr_FR.UTF-8'),
            datetime.date(2011, 1, 11)
        )

        self.assertEquals(current_locale, locale.getlocale(locale.LC_ALL))


if __name__ == '__main__':
    unittest.main()
