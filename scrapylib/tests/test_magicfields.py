import re, os
from unittest import TestCase

from scrapy.spider import BaseSpider
from scrapy.utils.test import get_crawler
from scrapy.item import DictItem, Field
from scrapy.http import HtmlResponse

from scrapylib.magicfields import _format, MagicFieldsMiddleware

class TestItem(DictItem):
    fields = {
        'url': Field(),
        'nom': Field(),
        'prix': Field(),
        'spider': Field(),
        'sku': Field(),
    }

class MagicFieldsTest(TestCase):
    
    def setUp(self):
        self.environ = os.environ.copy()
        self.spider = BaseSpider('myspider', arg1='val1', start_urls = ["http://example.com"])
        def _log(x):
            print x
        self.spider.log = _log
        self.response = HtmlResponse(body="<html></html>", url="http://www.example.com/product/8798732") 
        self.item = TestItem({'nom': 'myitem', 'prix': "56.70 euros", "url": "http://www.example.com/product.html?item_no=345"})

    def tearDown(self):
        os.environ = self.environ

    def assertRegexpMatches(self, text, regexp):
        """not present in python below 2.7"""
        return self.assertNotEqual(re.match(regexp, text), None)

    def test_hello(self):
        self.assertEqual(_format("hello world!", self.spider, self.response, self.item, {}), 'hello world!')

    def test_spidername_time(self):
        formatted = _format("Spider: $spider:name. Item scraped at $time", self.spider, self.response, self.item, {})
        self.assertRegexpMatches(formatted, 'Spider: myspider. Item scraped at \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')

    def test_unixtime(self):
        formatted = _format("Item scraped at $unixtime", self.spider, self.response, self.item, {})
        self.assertRegexpMatches(formatted, 'Item scraped at \d+\.\d+$')

    def test_isotime(self):
        formatted = _format("$isotime", self.spider, self.response, self.item, {})
        self.assertRegexpMatches(formatted, '\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}$')

    def test_jobid(self):
        os.environ["SCRAPY_JOB"] = 'aa788'
        formatted = _format("job id '$jobid' for spider $spider:name", self.spider, self.response, self.item, {})
        self.assertEqual(formatted, "job id 'aa788' for spider myspider")

    def test_spiderarg(self):
        formatted = _format("Argument arg1: $spider:arg1", self.spider, self.response, self.item, {})
        self.assertEqual(formatted, 'Argument arg1: val1')

    def test_spiderattr(self):
        formatted = _format("$spider:start_urls", self.spider, self.response, self.item, {})
        self.assertEqual(formatted, "['http://example.com']")

    def test_settings(self):
        formatted = _format("$setting:MY_SETTING", self.spider, self.response, self.item, {"$setting": {"MY_SETTING": True}})
        self.assertEqual(formatted, 'True')

    def test_notexisting(self):
        """Not existing entities are not substituted"""
        formatted = _format("Item scraped at $myentity", self.spider, self.response, self.item, {})
        self.assertEqual(formatted, 'Item scraped at $myentity')

    def test_noargs(self):
        """If entity does not accept arguments, don't substitute"""
        formatted = _format("Scraped on day $unixtime:arg", self.spider, self.response, self.item, {})
        self.assertEqual(formatted, "Scraped on day $unixtime:arg")

    def test_noargs2(self):
        """If entity does not have enough arguments, don't substitute"""
        formatted = _format("$spider", self.spider, self.response, self.item, {})
        self.assertEqual(formatted, "$spider")

    def test_invalidattr(self):
        formatted = _format("Argument arg2: $spider:arg2", self.spider, self.response, self.item, {})
        self.assertEqual(formatted, "Argument arg2: $spider:arg2")

    def test_environment(self):
        os.environ["TEST_ENV"] = "testval"
        formatted = _format("$env:TEST_ENV", self.spider, self.response, self.item, {})
        self.assertEqual(formatted, "testval")

    def test_response(self):
        formatted = _format("$response:url", self.spider, self.response, self.item, {})
        self.assertEqual(formatted, self.response.url)

    def test_fields_copy(self):
        formatted = _format("$field:nom", self.spider, self.response, self.item, {})
        self.assertEqual(formatted, 'myitem')

    def test_mware(self):
        settings = {"MAGIC_FIELDS": {"spider": "$spider:name"}}
        crawler = get_crawler(settings)
        mware = MagicFieldsMiddleware.from_crawler(crawler)
        result = list(mware.process_spider_output(self.response, [self.item], self.spider))[0]
        expected = {
            'nom': 'myitem',
            'prix': '56.70 euros',
            'spider': 'myspider',
            'url': 'http://www.example.com/product.html?item_no=345'
        }
        self.assertEqual(result, expected)

    def test_mware_override(self):
        settings = {
            "MAGIC_FIELDS": {"spider": "$spider:name"},
            "MAGIC_FIELDS_OVERRIDE": {"sku": "$field:nom"}
        }
        crawler = get_crawler(settings)
        mware = MagicFieldsMiddleware.from_crawler(crawler)
        result = list(mware.process_spider_output(self.response, [self.item], self.spider))[0]
        expected = {
            'nom': 'myitem',
            'prix': '56.70 euros',
            'spider': 'myspider',
            'url': 'http://www.example.com/product.html?item_no=345',
            'sku': 'myitem',
        }
        self.assertEqual(result, expected)
