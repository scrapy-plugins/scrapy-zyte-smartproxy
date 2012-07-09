from unittest import TestCase

from w3lib.http import basic_auth_header
from scrapy.http import Request, Response
from scrapy.spider import BaseSpider
from scrapy.utils.test import get_crawler
from scrapylib.hubproxy import HubProxyMiddleware


class HubProxyMiddlewareTestCase(TestCase):

    def setUp(self):
        self.spider = BaseSpider('foo')
        self.settings = {'HUBPROXY_USER': 'user', 'HUBPROXY_PASS': 'pass'}

    def _mock_crawler(self, settings=None):
        class MockedEngine(object):
            fake_spider_closed_result = None
            def close_spider(self, spider, reason):
                self.fake_spider_closed_result = (spider, reason)

        crawler = get_crawler(settings)
        crawler.engine = MockedEngine()
        return crawler

    def _assert_disabled(self, spider, settings=None):
        crawler = self._mock_crawler(settings)
        mw = HubProxyMiddleware.from_crawler(crawler)
        mw.open_spider(spider)
        req = Request('http://www.scrapytest.org')
        out = mw.process_request(req, spider)
        self.assertEqual(out, None)
        self.assertEqual(req.meta.get('proxy'), None)
        self.assertEqual(req.headers.get('Proxy-Authorization'), None)
        res = Response(req.url)
        assert mw.process_response(req, res, spider) is res

    def _assert_enabled(self, spider,
                        settings=None,
                        proxyurl='http://proxy.scrapinghub.com:8010',
                        basicauth=basic_auth_header('user', 'pass'),
                        bancode=503,
                        maxbans=20,
                        download_timeout=1800,
                       ):
        crawler = self._mock_crawler(settings)
        mw = HubProxyMiddleware.from_crawler(crawler)
        mw.open_spider(spider)
        req = Request('http://www.scrapytest.org')
        assert mw.process_request(req, spider) is None
        self.assertEqual(req.meta.get('proxy'), proxyurl)
        self.assertEqual(req.meta.get('download_timeout'), download_timeout)
        self.assertEqual(req.headers.get('Proxy-Authorization'), basicauth)
        res = Response(req.url)
        assert mw.process_response(req, res, spider) is res

        if maxbans > 0:
            # assert ban count is reseted after a succesful response
            res = Response('http://ban.me', status=bancode)
            assert mw.process_response(req, res, spider) is res
            self.assertEqual(crawler.engine.fake_spider_closed_result, None)
            res = Response('http://unban.me')
            assert mw.process_response(req, res, spider) is res
            self.assertEqual(crawler.engine.fake_spider_closed_result, None)

        # check for not banning before maxbans for bancode
        for x in xrange(maxbans + 1):
            self.assertEqual(crawler.engine.fake_spider_closed_result, None)
            res = Response('http://ban.me/%d' % x, status=bancode)
            assert mw.process_response(req, res, spider) is res

        # max bans reached and close_spider called
        self.assertEqual(crawler.engine.fake_spider_closed_result, (spider, 'banned'))

    def test_disabled_by_lack_of_hubproxy_settings(self):
        self._assert_disabled(self.spider, settings={})

    def test_spider_use_hubproxy(self):
        self.assertFalse(hasattr(self.spider, 'use_hubproxy'))
        self._assert_disabled(self.spider, self.settings)
        self.spider.use_hubproxy = True
        self._assert_enabled(self.spider, self.settings)
        self.spider.use_hubproxy = False
        self._assert_disabled(self.spider, self.settings)

    def test_shub_job_tags(self):
        self.settings['SHUB_JOB_TAGS'] = 'other'
        self._assert_disabled(self.spider, self.settings)
        self.settings['SHUB_JOB_TAGS'] = 'hubproxy'
        self._assert_enabled(self.spider, self.settings)

    def test_userpass(self):
        self.spider.use_hubproxy = True
        self.settings['HUBPROXY_USER'] = user = 'other'
        self.settings['HUBPROXY_PASS'] = pass_ = 'secret'
        basicauth = basic_auth_header(user, pass_)
        self._assert_enabled(self.spider, self.settings, basicauth=basicauth)

        self.spider.hubproxy_user = user = 'notfromsettings'
        self.spider.hubproxy_pass = pass_ = 'anothersecret'
        basicauth = basic_auth_header(user, pass_)
        self._assert_enabled(self.spider, self.settings, basicauth=basicauth)

    def test_proxyurl(self):
        self.spider.use_hubproxy = True
        self.settings['HUBPROXY_URL'] = proxyurl = 'http://localhost:8010'
        self._assert_enabled(self.spider, self.settings, proxyurl=proxyurl)

    def test_maxbans(self):
        self.spider.use_hubproxy = True
        self.settings['HUBPROXY_MAXBANS'] = maxbans = 0
        self._assert_enabled(self.spider, self.settings, maxbans=maxbans)
        self.settings['HUBPROXY_MAXBANS'] = maxbans = 100
        self._assert_enabled(self.spider, self.settings, maxbans=maxbans)

    def test_download_timeout(self):
        self.spider.use_hubproxy = True
        self.settings['HUBPROXY_DOWNLOAD_TIMEOUT'] = 60
        self._assert_enabled(self.spider, self.settings, download_timeout=60)
        self.spider.hubproxy_download_timeout = 120
        self._assert_enabled(self.spider, self.settings, download_timeout=120)
