from unittest import TestCase

from w3lib.http import basic_auth_header
from scrapy.http import Request, Response
from scrapy.spiders import Spider
from scrapy.utils.test import get_crawler
from scrapy.resolver import dnscache
from twisted.internet.error import ConnectionRefusedError, ConnectionDone

from scrapy_crawlera import CrawleraMiddleware
import os


class MockedSlot(object):

    def __init__(self, delay=0.0):
        self.delay = delay


class CrawleraMiddlewareTestCase(TestCase):

    mwcls = CrawleraMiddleware
    bancode = 503

    def setUp(self):
        self.spider = Spider('foo')
        self.settings = {'CRAWLERA_USER': 'user', 'CRAWLERA_PASS': 'pass'}

    def _mock_crawler(self, spider, settings=None):

        class MockedDownloader(object):
            slots = {}

        class MockedEngine(object):
            downloader = MockedDownloader()
            fake_spider_closed_result = None

            def close_spider(self, spider, reason):
                self.fake_spider_closed_result = (spider, reason)

        crawler = get_crawler(spider, settings)
        crawler.engine = MockedEngine()
        return crawler

    def _assert_disabled(self, spider, settings=None):
        crawler = self._mock_crawler(spider, settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        req = Request('http://www.scrapytest.org')
        out = mw.process_request(req, spider)
        self.assertEqual(out, None)
        self.assertEqual(req.meta.get('proxy'), None)
        self.assertEqual(req.meta.get('download_timeout'), None)
        self.assertEqual(req.headers.get('Proxy-Authorization'), None)
        res = Response(req.url)
        assert mw.process_response(req, res, spider) is res
        res = Response(req.url, status=mw.ban_code)
        assert mw.process_response(req, res, spider) is res

    def _assert_enabled(self, spider,
                        settings=None,
                        proxyurl='http://proxy.crawlera.com:8010',
                        proxyauth=basic_auth_header('user', 'pass'),
                        maxbans=400,
                        download_timeout=190):
        crawler = self._mock_crawler(spider, settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        req = Request('http://www.scrapytest.org')
        assert mw.process_request(req, spider) is None
        self.assertEqual(req.meta.get('proxy'), proxyurl)
        self.assertEqual(req.meta.get('download_timeout'), download_timeout)
        self.assertEqual(req.headers.get('Proxy-Authorization'), proxyauth)
        res = Response(req.url)
        assert mw.process_response(req, res, spider) is res

        # disabled if 'dont_proxy' is set
        req = Request('http://www.scrapytest.org')
        req.meta['dont_proxy'] = True
        assert mw.process_request(req, spider) is None
        self.assertEqual(req.meta.get('proxy'), None)
        self.assertEqual(req.meta.get('download_timeout'), None)
        self.assertEqual(req.headers.get('Proxy-Authorization'), None)
        res = Response(req.url)
        assert mw.process_response(req, res, spider) is res
        del req.meta['dont_proxy']

        if maxbans > 0:
            # assert ban count is reseted after a succesful response
            res = Response('http://ban.me', status=self.bancode)
            assert mw.process_response(req, res, spider) is res
            self.assertEqual(crawler.engine.fake_spider_closed_result, None)
            res = Response('http://unban.me')
            assert mw.process_response(req, res, spider) is res
            self.assertEqual(crawler.engine.fake_spider_closed_result, None)
            self.assertEqual(mw._bans[None], 0)

        # check for not banning before maxbans for bancode
        for x in range(maxbans + 1):
            self.assertEqual(crawler.engine.fake_spider_closed_result, None)
            res = Response('http://ban.me/%d' % x, status=self.bancode)
            assert mw.process_response(req, res, spider) is res

        # max bans reached and close_spider called
        self.assertEqual(crawler.engine.fake_spider_closed_result, (spider, 'banned'))

    def test_disabled_by_lack_of_crawlera_settings(self):
        self._assert_disabled(self.spider, settings={})

    def test_spider_crawlera_enabled(self):
        self.assertFalse(hasattr(self.spider, 'crawlera_enabled'))
        self._assert_disabled(self.spider, self.settings)
        self.spider.crawlera_enabled = True
        self._assert_enabled(self.spider, self.settings)
        self.spider.crawlera_enabled = False
        self._assert_disabled(self.spider, self.settings)

    def test_enabled(self):
        self._assert_disabled(self.spider, self.settings)
        self.settings['CRAWLERA_ENABLED'] = True
        self._assert_enabled(self.spider, self.settings)

    def test_userpass(self):
        self.spider.crawlera_enabled = True
        self.settings['CRAWLERA_USER'] = user = 'other'
        self.settings['CRAWLERA_PASS'] = pass_ = 'secret'
        proxyauth = basic_auth_header(user, pass_)
        self._assert_enabled(self.spider, self.settings, proxyauth=proxyauth)

        self.spider.crawlera_user = user = 'notfromsettings'
        self.spider.crawlera_pass = pass_ = 'anothersecret'
        proxyauth = basic_auth_header(user, pass_)
        self._assert_enabled(self.spider, self.settings, proxyauth=proxyauth)

    def test_proxyurl(self):
        self.spider.crawlera_enabled = True
        self.settings['CRAWLERA_URL'] = 'http://localhost:8010'
        self._assert_enabled(self.spider, self.settings, proxyurl='http://localhost:8010')

    def test_proxyurl_including_noconnect(self):
        self.spider.crawlera_enabled = True
        self.settings['CRAWLERA_URL'] = 'http://localhost:8010?noconnect'
        self._assert_enabled(self.spider, self.settings, proxyurl='http://localhost:8010?noconnect')

    def test_maxbans(self):
        self.spider.crawlera_enabled = True
        self.settings['CRAWLERA_MAXBANS'] = maxbans = 0
        self._assert_enabled(self.spider, self.settings, maxbans=maxbans)
        self.settings['CRAWLERA_MAXBANS'] = maxbans = 100
        self._assert_enabled(self.spider, self.settings, maxbans=maxbans)
        # Assert setting is coerced into correct type
        self.settings['CRAWLERA_MAXBANS'] = '123'
        self._assert_enabled(self.spider, self.settings, maxbans=123)
        self.spider.crawlera_maxbans = 99
        self._assert_enabled(self.spider, self.settings, maxbans=99)

    def test_download_timeout(self):
        self.spider.crawlera_enabled = True
        self.settings['CRAWLERA_DOWNLOAD_TIMEOUT'] = 60
        self._assert_enabled(self.spider, self.settings, download_timeout=60)
        # Assert setting is coerced into correct type
        self.settings['CRAWLERA_DOWNLOAD_TIMEOUT'] = '42'
        self._assert_enabled(self.spider, self.settings, download_timeout=42)
        self.spider.crawlera_download_timeout = 120
        self._assert_enabled(self.spider, self.settings, download_timeout=120)

    def test_hooks(self):
        class _ECLS(self.mwcls):
            def is_enabled(self, spider):
                wascalled.append('is_enabled')
                return enabled

            def get_proxyauth(self, spider):
                wascalled.append('get_proxyauth')
                return proxyauth

        wascalled = []
        self.mwcls = _ECLS

        # test is_enabled returns False
        enabled = False
        self.spider.crawlera_enabled = True
        self._assert_disabled(self.spider, self.settings)
        self.assertEqual(wascalled, ['is_enabled'])

        wascalled[:] = []  # reset
        enabled = True
        self.spider.crawlera_enabled = False
        proxyauth = b'Basic Foo'
        self._assert_enabled(self.spider, self.settings, proxyauth=proxyauth)
        self.assertEqual(wascalled, ['is_enabled', 'get_proxyauth'])

    def test_delay_adjustment(self):
        delay = 0.5
        slot_key = 'www.scrapytest.org'
        url = 'http://www.scrapytest.org'
        ban_url = 'http://ban.me'

        self.spider.crawlera_enabled = True

        crawler = self._mock_crawler(self.spider, self.settings)
        # ignore spider delay by default
        self.spider.download_delay = delay
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        self.assertEqual(self.spider.download_delay, 0)

        # preserve original delay
        self.spider.download_delay = delay
        self.spider.crawlera_preserve_delay = True
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        self.assertEqual(self.spider.download_delay, delay)

        slot = MockedSlot(self.spider.download_delay)
        crawler.engine.downloader.slots[slot_key] = slot

        # ban
        req = Request(url, meta={'download_slot': slot_key})
        res = Response(ban_url, status=self.bancode, request=req)
        mw.process_response(req, res, self.spider)
        self.assertEqual(slot.delay, delay)
        self.assertEqual(self.spider.download_delay, delay)

        retry_after = 1.5
        headers = {'retry-after': str(retry_after)}
        res = Response(
            ban_url, status=self.bancode, headers=headers, request=req)
        mw.process_response(req, res, self.spider)
        self.assertEqual(slot.delay, retry_after)
        self.assertEqual(self.spider.download_delay, delay)

        # DNS cache should be cleared in case of errors
        dnscache['proxy.crawlera.com'] = '1.1.1.1'

        res = Response(url, request=req)
        mw.process_response(req, res, self.spider)
        self.assertEqual(slot.delay, delay)
        self.assertEqual(self.spider.download_delay, delay)
        self.assertIn('proxy.crawlera.com', dnscache)

        # server failures
        mw.process_exception(req, ConnectionRefusedError(), self.spider)
        self.assertEqual(slot.delay, mw.connection_refused_delay)
        self.assertEqual(self.spider.download_delay, delay)
        self.assertNotIn('proxy.crawlera.com', dnscache)

        dnscache['proxy.crawlera.com'] = '1.1.1.1'
        res = Response(ban_url, request=req)
        mw.process_response(req, res, self.spider)
        self.assertEqual(slot.delay, delay)
        self.assertEqual(self.spider.download_delay, delay)
        self.assertIn('proxy.crawlera.com', dnscache)

        mw.process_exception(req, ConnectionRefusedError(), self.spider)
        self.assertEqual(slot.delay, mw.connection_refused_delay)
        self.assertEqual(self.spider.download_delay, delay)
        self.assertNotIn('proxy.crawlera.com', dnscache)

        dnscache['proxy.crawlera.com'] = '1.1.1.1'
        res = Response(ban_url, status=self.bancode, request=req)
        mw.process_response(req, res, self.spider)
        self.assertEqual(slot.delay, delay)
        self.assertEqual(self.spider.download_delay, delay)
        self.assertIn('proxy.crawlera.com', dnscache)

        mw.process_exception(req, ConnectionDone(), self.spider)
        self.assertEqual(slot.delay, mw.connection_refused_delay)
        self.assertEqual(self.spider.download_delay, delay)
        self.assertNotIn('proxy.crawlera.com', dnscache)

    def test_jobid_header(self):
        # test without the environment variable 'SCRAPY_JOB'
        self.spider.crawlera_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        req = Request('http://www.scrapytest.org')
        self.assertEqual(mw.process_request(req, self.spider), None)
        self.assertEqual(req.headers.get('X-Crawlera-Jobid'), None)

        # test with the environment variable 'SCRAPY_JOB'
        os.environ['SCRAPY_JOB'] = '2816'
        self.spider.crawlera_enabled = True
        crawler1 = self._mock_crawler(self.spider, self.settings)
        mw1 = self.mwcls.from_crawler(crawler)
        mw1.open_spider(self.spider)
        req1 = Request('http://www.scrapytest.org')
        self.assertEqual(mw1.process_request(req1, self.spider), None)
        self.assertEqual(req1.headers.get('X-Crawlera-Jobid'), b'2816')

    def test_apikey_assignment(self):
        self.spider.crawlera_enabled = True

        apikey = 'someapikey'
        self.settings['CRAWLERA_APIKEY'] = None
        self.settings['CRAWLERA_USER'] = apikey
        self.settings['CRAWLERA_PASS'] = ''
        proxyauth = basic_auth_header(apikey, '')
        self._assert_enabled(self.spider, self.settings, proxyauth=proxyauth)

        self.settings['CRAWLERA_USER'] = None
        self.settings['CRAWLERA_APIKEY'] = apikey
        self.settings['CRAWLERA_PASS'] = ''
        proxyauth = basic_auth_header(apikey, '')
        self._assert_enabled(self.spider, self.settings, proxyauth=proxyauth)

    def test_stats(self):
        self.spider.crawlera_enabled = True
        spider = self.spider
        crawler = self._mock_crawler(spider, None)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)

        req = Request('http://www.scrapytest.org')
        assert mw.process_request(req, spider) is None
        self.assertEqual(crawler.stats.get_value('crawlera/request'), 1)
        self.assertEqual(crawler.stats.get_value('crawlera/request/method/GET'), 1)

        res = Response(req.url)
        assert mw.process_response(req, res, spider) is res
        self.assertEqual(crawler.stats.get_value('crawlera/response'), 1)
        self.assertEqual(crawler.stats.get_value('crawlera/response/status/200'), 1)

        req = Request('http://www.scrapytest.org/other', method='POST')
        assert mw.process_request(req, spider) is None
        self.assertEqual(crawler.stats.get_value('crawlera/request'), 2)
        self.assertEqual(crawler.stats.get_value('crawlera/request/method/POST'), 1)

        res = Response(req.url, status=mw.ban_code, headers={'X-Crawlera-Error': 'somethingbad'})
        assert mw.process_response(req, res, spider) is res
        self.assertEqual(crawler.stats.get_value('crawlera/response'), 2)
        self.assertEqual(crawler.stats.get_value('crawlera/response/status/{}'.format(mw.ban_code)), 1)
        self.assertEqual(crawler.stats.get_value('crawlera/response/banned'), 1)
        self.assertEqual(crawler.stats.get_value('crawlera/response/error/somethingbad'), 1)

    def _make_fake_request(self, spider, crawlera_enabled):
        spider.crawlera_enabled = crawlera_enabled
        crawler = self._mock_crawler(spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        headers = {
            'X-Crawlera-Debug': True,
            'X-Crawlera-Profile': 'desktop',
            'User-Agent': 'Scrapy'
        }
        req = Request('http://www.scrapytest.org', headers=headers)
        out = mw.process_request(req, spider)
        return req

    def test_clean_headers_when_disabled(self):
        req = self._make_fake_request(self.spider, crawlera_enabled=False)

        self.assertNotIn(b'X-Crawlera-Debug', req.headers)
        self.assertNotIn(b'X-Crawlera-Profile', req.headers)
        self.assertIn(b'User-Agent', req.headers)

    def test_clean_headers_when_enabled(self):
        req = self._make_fake_request(self.spider, crawlera_enabled=True)

        self.assertIn(b'X-Crawlera-Debug', req.headers)
        self.assertIn(b'X-Crawlera-Profile', req.headers)
        self.assertIn(b'User-Agent', req.headers)
