import re, os
from unittest import TestCase

from scrapy.spider import BaseSpider

from scrapylib.magicfields import _format

class MagicFieldsTest(TestCase):
    
    def setUp(self):
        self.environ = os.environ.copy()
        self.spider = BaseSpider('myspider', arg1='val1', start_urls = ["http://example.com"])

    def tearDown(self):
        os.environ = self.environ

    def assertRegexpMatches(self, text, regexp):
        """not present in python below 2.7"""
        return self.assertNotEqual(re.match(regexp, text), None)

    def test_hello(self):
        self.assertEqual(_format("hello world!", self.spider, {}), 'hello world!')

    def test_spidername_time(self):
        formatted = _format("Spider: $spider:name. Item scraped at $time", self.spider, {})
        self.assertRegexpMatches(formatted, 'Spider: myspider. Item scraped at \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')

    def test_unixtime(self):
        formatted = _format("Item scraped at $unixtime", self.spider, {})
        self.assertRegexpMatches(formatted, 'Item scraped at \d+\.\d+$')

    def test_isotime(self):
        formatted = _format("$isotime", self.spider, {})
        self.assertRegexpMatches(formatted, '\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}$')

    def test_jobid(self):
        os.environ["SCRAPY_JOB"] = 'aa788'
        formatted = _format("job id '$jobid' for spider $spider:name", self.spider, {})
        self.assertEqual(formatted, "job id 'aa788' for spider myspider")

    def test_spiderarg(self):
        formatted = _format("Argument arg1: $spider:arg1", self.spider, {})
        self.assertEqual(formatted, 'Argument arg1: val1')

    def test_spiderattr(self):
        formatted = _format("$spider:start_urls", self.spider, {})
        self.assertEqual(formatted, "['http://example.com']")

    def test_settings(self):
        formatted = _format("$setting:MY_SETTING", self.spider, {"$setting": {"MY_SETTING": True}})
        self.assertEqual(formatted, 'True')

    def test_notexisting(self):
        """Not existing entities are not substituted"""
        formatted = _format("Item scraped at $myentity", self.spider, {})
        self.assertEqual(formatted, 'Item scraped at $myentity')

    def test_noargs(self):
        """If entity does not accept arguments, don't substitute"""
        formatted = _format("Scraped on day $unixtime:arg", self.spider, {})
        self.assertEqual(formatted, "Scraped on day $unixtime:arg")

    def test_invalidattr(self):
        formatted = _format("Argument arg2: $spider:arg2", self.spider, {})
        self.assertEqual(formatted, "Argument arg2: $spider:arg2")

    def test_environment(self):
        os.environ["TEST_ENV"] = "testval"
        formatted = _format("$env:TEST_ENV", self.spider, {})
        self.assertEqual(formatted, "testval")
