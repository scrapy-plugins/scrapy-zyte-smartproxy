from unittest import TestCase

from scrapy.http import Request, Response
from scrapy.spider import BaseSpider
from scrapy.utils.test import get_crawler
from scrapylib.querycleaner import QueryCleanerMiddleware
from scrapy.exceptions import NotConfigured

class QueryCleanerTestCase(TestCase):

    mwcls = QueryCleanerMiddleware

    def setUp(self):
        self.spider = BaseSpider('foo')

    def test_not_loaded(self):
        crawler = get_crawler({})
        self.assertRaises(NotConfigured, self.mwcls.from_crawler, crawler)
        
    def test_filter_keep(self):
        crawler = get_crawler({"QUERYCLEANER_KEEP": "qxp"})
        mw = self.mwcls.from_crawler(crawler)
        response = Response(url="http://www.example.com/qxg1231")
        request = Request(url="http://www.example.com/product/?qxp=12&qxg=1231")
        new_request = list(mw.process_spider_output(response, [request], self.spider))[0]
        self.assertEqual(new_request.url, "http://www.example.com/product/?qxp=12")
        self.assertNotEqual(request, new_request)

    def test_filter_remove(self):
        crawler = get_crawler({"QUERYCLEANER_REMOVE": "qxg"})
        mw = self.mwcls.from_crawler(crawler)
        response = Response(url="http://www.example.com/qxg1231")
        request = Request(url="http://www.example.com/product/?qxp=12&qxg=1231")
        new_request = list(mw.process_spider_output(response, [request], self.spider))[0]
        self.assertEqual(new_request.url, "http://www.example.com/product/?qxp=12")
        self.assertNotEqual(request, new_request)
