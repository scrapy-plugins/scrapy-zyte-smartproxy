import os
import hashlib
from unittest import TestCase

from scrapy.http import Request, Response
from scrapy.spider import BaseSpider
from scrapy.utils.test import get_crawler
from scrapylib.hcf import HcfMiddleware
from scrapy.exceptions import NotConfigured, DontCloseSpider
from hubstorage import HubstorageClient


class HcfTestCase(TestCase):

    hcf_cls = HcfMiddleware

    projectid = '2222222'
    spidername = 'hs-test-spider'
    endpoint = os.getenv('HS_ENDPOINT', 'http://localhost:8003')
    auth = os.getenv('HS_AUTH', 'useavalidkey')
    frontier = 'test'
    slot = 'slot'

    @classmethod
    def setUpClass(cls):
        cls.hsclient = HubstorageClient(auth=cls.auth, endpoint=cls.endpoint)
        cls.project = cls.hsclient.get_project(cls.projectid)
        cls.fclient = cls.project.frontier

    @classmethod
    def tearDownClass(cls):
        cls.project.frontier.close()
        cls.hsclient.close()

    def setUp(self):

        class TestSpider(BaseSpider):
            name = self.spidername
            start_urls = [
                'http://www.example.com/'
            ]

        self.spider = TestSpider()
        self.hcf_settings = {'HS_ENDPOINT': self.endpoint,
                             'HS_AUTH': self.auth,
                             'HS_PROJECTID': self.projectid,
                             'HS_FRONTIER': self.frontier,
                             'HS_SLOT': self.slot}
        self._delete_slot()

    def tearDown(self):
        self._delete_slot()

    def _delete_slot(self):
        self.fclient.delete_slot(self.frontier, self.slot)

    def _build_response(self, url, meta=None):
        return Response(url, request=Request(url="http://www.example.com/parent.html", meta=meta))

    def _get_crawler(self, settings=None):
        crawler = get_crawler(settings)
        # simulate crawler engine
        class Engine():
            def __init__(self):
                self.requests = []
            def schedule(self, request, spider):
                self.requests.append(request)
        crawler.engine = Engine()

        return crawler

    def test_not_loaded(self):
        crawler = self._get_crawler({})
        self.assertRaises(NotConfigured, self.hcf_cls.from_crawler, crawler)

    def test_start_requests(self):
        crawler = self._get_crawler(self.hcf_settings)
        hcf = self.hcf_cls.from_crawler(crawler)

        # first time should be empty
        start_urls = self.spider.start_urls
        new_urls = list(hcf.process_start_requests(start_urls, self.spider))
        self.assertEqual(new_urls, ['http://www.example.com/'])

        # now try to store some URLs in the hcf and retrieve them
        fps = [{'fp': 'http://www.example.com/index.html'},
               {'fp': 'http://www.example.com/index2.html'}]
        self.fclient.add(self.frontier, self.slot, fps)
        self.fclient.flush()
        new_urls = [r.url for r in hcf.process_start_requests(start_urls, self.spider)]
        expected_urls = [r['fp'] for r in fps]
        self.assertEqual(new_urls, expected_urls)
        self.assertEqual(len(hcf.batch_ids), 1)

    def test_spider_output(self):
        crawler = self._get_crawler(self.hcf_settings)
        hcf = self.hcf_cls.from_crawler(crawler)

        # process new GET request
        response = self._build_response("http://www.example.com/qxg1231")
        request = Request(url="http://www.example.com/product/?qxp=12&qxg=1231")
        outputs = list(hcf.process_spider_output(response, [request], self.spider))
        self.assertEqual(outputs, [])
        expected_links = {'slot': ['http://www.example.com/product/?qxp=12&qxg=1231']}
        self.assertEqual(dict(hcf.new_links), expected_links)

        # process new POST request (don't add it to the hcf)
        response = self._build_response("http://www.example.com/qxg456")
        request = Request(url="http://www.example.com/product/?qxp=456", method='POST')
        outputs = list(hcf.process_spider_output(response, [request], self.spider))
        self.assertEqual(outputs, [request])
        expected_links = {'slot': ['http://www.example.com/product/?qxp=12&qxg=1231']}
        self.assertEqual(dict(hcf.new_links), expected_links)

        # process new GET request (with the skip_hcf meta key)
        response = self._build_response("http://www.example.com/qxg1231", meta={'skip_hcf': True})
        request = Request(url="http://www.example.com/product/?qxp=789")
        outputs = list(hcf.process_spider_output(response, [request], self.spider))
        self.assertEqual(outputs, [request])
        expected_links = {'slot': ['http://www.example.com/product/?qxp=12&qxg=1231']}
        self.assertEqual(dict(hcf.new_links), expected_links)

    def test_idle_close_spider(self):
        crawler = self._get_crawler(self.hcf_settings)
        hcf = self.hcf_cls.from_crawler(crawler)

        # Save 2 batches in the HCF
        fps = [{'fp': 'http://www.example.com/index_%s.html' % i} for i in range(0, 200)]
        self.fclient.add(self.frontier, self.slot, fps)
        self.fclient.flush()

        # Read the first batch
        start_urls = self.spider.start_urls
        new_urls = [r.url for r in hcf.process_start_requests(start_urls, self.spider)]
        expected_urls = [r['fp'] for r in fps[:100]]
        self.assertEqual(new_urls, expected_urls)

        # Simulate extracting some new urls
        response = self._build_response("http://www.example.com/parent.html")
        new_fps = ["http://www.example.com/child_%s.html" % i for i in range(0, 50)]
        for fp in new_fps:
            request = Request(url=fp)
            list(hcf.process_spider_output(response, [request], self.spider))
        self.assertEqual(len(hcf.new_links[self.slot]), 50)

        # Simulate emptying the scheduler
        crawler.engine.requests = []

        # Simulate idle spider
        self.assertRaises(DontCloseSpider, hcf.idle_spider, self.spider)
        new_urls = [r.url for r in crawler.engine.requests]
        self.assertEqual(len(hcf.new_links[self.slot]), 0)
        self.assertEqual(len(hcf.batch_ids), 1)
        self.assertEqual(len(new_urls), 100)
        expected_urls = [r['fp'] for r in fps[100:200]]
        self.assertEqual(new_urls, expected_urls)
        # need to flush the client so the 50 new urls are picked by
        # the next call to idle_spider
        hcf.fclient.flush()

        # Simulate emptying the scheduler
        crawler.engine.requests = []

        # Simulate idle spider (get the 50 additional URLs)
        self.assertRaises(DontCloseSpider, hcf.idle_spider, self.spider)
        new_urls = [r.url for r in crawler.engine.requests]
        self.assertEqual(len(hcf.new_links[self.slot]), 0)
        self.assertEqual(len(hcf.batch_ids), 1)
        self.assertEqual(len(new_urls), 50)
        self.assertEqual(new_urls, new_fps)

        # Simulate close spider
        hcf.close_spider(self.spider)
        self.assertEqual(len(hcf.new_links[self.slot]), 0)
        self.assertEqual(len(hcf.batch_ids), 0)

        # HCF must be empty now
        batches = [b for b in self.fclient.read(self.frontier, self.slot)]
        self.assertEqual(len(batches), 0)

    def test_spider_output_override_slot(self):
        crawler = self._get_crawler(self.hcf_settings)
        hcf = self.hcf_cls.from_crawler(crawler)

        def get_slot_callback(request):
            md5 = hashlib.md5()
            md5.update(request.url)
            digest = md5.hexdigest()
            return str(int(digest, 16) % 5)

        # process new GET request
        response = self._build_response("http://www.example.com/qxg1231",
                                        meta={'slot_callback': get_slot_callback})
        request = Request(url="http://www.example.com/product/?qxp=12&qxg=1231")
        outputs = list(hcf.process_spider_output(response, [request], self.spider))
        self.assertEqual(outputs, [])
        expected_links = {'4': ['http://www.example.com/product/?qxp=12&qxg=1231']}
        self.assertEqual(dict(hcf.new_links), expected_links)


