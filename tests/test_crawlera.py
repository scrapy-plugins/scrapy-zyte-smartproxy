from unittest import TestCase
try:
    from unittest.mock import call, patch
except ImportError:
    from mock import call, patch

from w3lib.http import basic_auth_header
from scrapy.http import Request, Response
from scrapy.spiders import Spider
from scrapy.utils.test import get_crawler
from scrapy.resolver import dnscache
from twisted.internet.error import ConnectionRefusedError, ConnectionDone

from scrapy_crawlera import CrawleraMiddleware
import os

from scrapy_crawlera.utils import exp_backoff


class MockedSlot(object):

    def __init__(self, delay=0.0):
        self.delay = delay


class CrawleraMiddlewareTestCase(TestCase):

    mwcls = CrawleraMiddleware
    bancode = 503

    def setUp(self):
        self.spider = Spider('foo')
        self.settings = {'CRAWLERA_APIKEY': 'apikey'}

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
                        proxyauth=basic_auth_header('apikey', ''),
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

        # disabled if 'dont_proxy=True' is set
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
            res = Response(
                'http://ban.me/%d' % x,
                status=self.bancode,
                headers={'X-Crawlera-Error': 'banned'},
            )
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

    def test_apikey(self):
        self.spider.crawlera_enabled = True
        self.settings['CRAWLERA_APIKEY'] = apikey = 'apikey'
        proxyauth = basic_auth_header(apikey, '')
        self._assert_enabled(self.spider, self.settings, proxyauth=proxyauth)

        self.spider.crawlera_apikey = apikey = 'notfromsettings'
        proxyauth = basic_auth_header(apikey, '')
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

        # ban without retry-after
        req = Request(url, meta={'download_slot': slot_key})
        headers = {'X-Crawlera-Error': 'banned'}
        res = Response(
            ban_url, status=self.bancode, headers=headers, request=req)
        mw.process_response(req, res, self.spider)
        self.assertEqual(slot.delay, delay)
        self.assertEqual(self.spider.download_delay, delay)

        # ban with retry-after
        retry_after = 1.5
        headers = {
            'retry-after': str(retry_after),
            'X-Crawlera-Error': 'banned'
        }
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

    def test_stats(self):
        self.spider.crawlera_enabled = True
        spider = self.spider
        crawler = self._mock_crawler(spider, self.settings)
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
        self.assertEqual(crawler.stats.get_value('crawlera/response/error/somethingbad'), 1)
        res = Response(req.url, status=mw.ban_code, headers={'X-Crawlera-Error': 'banned'})
        assert mw.process_response(req, res, spider) is res
        self.assertEqual(crawler.stats.get_value('crawlera/response'), 3)
        self.assertEqual(crawler.stats.get_value('crawlera/response/status/{}'.format(mw.ban_code)), 2)
        self.assertEqual(crawler.stats.get_value('crawlera/response/banned'), 1)

    def _make_fake_request(self, spider, crawlera_enabled):
        spider.crawlera_enabled = crawlera_enabled
        crawler = self._mock_crawler(spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        headers = {
            'X-Crawlera-Debug': True,
            'X-Crawlera-Profile': 'desktop',
            'User-Agent': 'Scrapy',
            '': None,
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

    def test_crawlera_default_headers(self):
        spider = self.spider
        self.spider.crawlera_enabled = True

        self.settings['CRAWLERA_DEFAULT_HEADERS'] = {
            'X-Crawlera-Profile': 'desktop',
        }
        crawler = self._mock_crawler(spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        req = Request('http://www.scrapytest.org/other')
        assert mw.process_request(req, spider) is None
        self.assertEqual(req.headers['X-Crawlera-Profile'], b'desktop')

        # test ignore None headers
        self.settings['CRAWLERA_DEFAULT_HEADERS'] = {
            'X-Crawlera-Profile': None,
            'X-Crawlera-Cookies': 'disable',
        }
        crawler = self._mock_crawler(spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        req = Request('http://www.scrapytest.org/other')
        assert mw.process_request(req, spider) is None
        self.assertEqual(req.headers['X-Crawlera-Cookies'], b'disable')
        self.assertNotIn('X-Crawlera-Profile', req.headers)

    @patch('scrapy_crawlera.middleware.logging')
    def test_crawlera_default_headers_conflicting_headers(self, mock_logger):
        spider = self.spider
        self.spider.crawlera_enabled = True

        self.settings['CRAWLERA_DEFAULT_HEADERS'] = {
            'X-Crawlera-Profile': 'desktop',
        }
        crawler = self._mock_crawler(spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)

        req = Request('http://www.scrapytest.org/other',
                      headers={'X-Crawlera-UA': 'desktop'})
        assert mw.process_request(req, spider) is None
        self.assertEqual(req.headers['X-Crawlera-UA'], b'desktop')
        self.assertEqual(req.headers['X-Crawlera-Profile'], b'desktop')
        mock_logger.debug.assert_called_with(
            "The headers ('X-Crawlera-Profile', 'X-Crawlera-UA') are conflictin"
            "g on request http://www.scrapytest.org/other. X-Crawlera-UA will b"
            "e ignored. Please check https://doc.scrapinghub.com/crawlera.html "
            "for more information",
            extra={'spider': spider}
        )

        # test it ignores case
        req = Request('http://www.scrapytest.org/other',
                      headers={'x-crawlera-ua': 'desktop'})
        assert mw.process_request(req, spider) is None
        self.assertEqual(req.headers['X-Crawlera-UA'], b'desktop')
        self.assertEqual(req.headers['X-Crawlera-Profile'], b'desktop')
        mock_logger.debug.assert_called_with(
            "The headers ('X-Crawlera-Profile', 'X-Crawlera-UA') are conflictin"
            "g on request http://www.scrapytest.org/other. X-Crawlera-UA will b"
            "e ignored. Please check https://doc.scrapinghub.com/crawlera.html "
            "for more information",
            extra={'spider': spider}
        )

    def test_dont_proxy_false_does_nothing(self):
        spider = self.spider
        spider.crawlera_enabled = True
        crawler = self._mock_crawler(spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        req = Request('http://www.scrapytest.org/other')
        req.meta['dont_proxy'] = False
        assert mw.process_request(req, spider) is None
        self.assertIsNotNone(req.meta.get('proxy'))

    def test_is_banned(self):
        self.spider.crawlera_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        req = self._make_fake_request(self.spider, crawlera_enabled=True)
        res = Response(req.url, status=200)
        self.assertFalse(mw._is_banned(res))
        res = Response(req.url, status=503, headers={'X-Crawlera-Error': 'noslaves'})
        self.assertFalse(mw._is_banned(res))
        res = Response(req.url, status=503, headers={'X-Crawlera-Error': 'banned'})
        self.assertTrue(mw._is_banned(res))

    @patch('random.uniform')
    def test_noslaves_delays(self, random_uniform_patch):
        # mock random.uniform to just return the max delay
        random_uniform_patch.side_effect = lambda x, y: y

        slot_key = 'www.scrapytest.org'
        url = 'http://www.scrapytest.org'
        ban_url = 'http://ban.me'
        max_delay = 70
        backoff_step = 15
        default_delay = 0

        self.settings['CRAWLERA_BACKOFF_STEP'] = backoff_step
        self.settings['CRAWLERA_BACKOFF_MAX'] = max_delay

        self.spider.crawlera_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        mw.noslaves_max_delay = max_delay

        slot = MockedSlot()
        crawler.engine.downloader.slots[slot_key] = slot

        noslaves_req = Request(url, meta={'download_slot': slot_key})
        headers = {'X-Crawlera-Error': 'noslaves'}
        noslaves_res = Response(
            ban_url, status=self.bancode, headers=headers, request=noslaves_req)

        # delays grow exponentially
        mw.process_response(noslaves_req, noslaves_res, self.spider)
        self.assertEqual(slot.delay, backoff_step)

        mw.process_response(noslaves_req, noslaves_res, self.spider)
        self.assertEqual(slot.delay, backoff_step * 2 ** 1)

        mw.process_response(noslaves_req, noslaves_res, self.spider)
        self.assertEqual(slot.delay, backoff_step * 2 ** 2)

        mw.process_response(noslaves_req, noslaves_res, self.spider)
        self.assertEqual(slot.delay, max_delay)

        # other responses reset delay
        ban_req = Request(url, meta={'download_slot': slot_key})
        ban_headers = {'X-Crawlera-Error': 'banned'}
        ban_res = Response(
            ban_url, status=self.bancode, headers=ban_headers, request=ban_req)
        mw.process_response(ban_req, ban_res, self.spider)
        self.assertEqual(slot.delay, default_delay)

        mw.process_response(noslaves_req, noslaves_res, self.spider)
        self.assertEqual(slot.delay, backoff_step)

        good_req = Request(url, meta={'download_slot': slot_key})
        good_res = Response(
            url, status=200, request=good_req)
        mw.process_response(good_req, good_res, self.spider)
        self.assertEqual(slot.delay, default_delay)

    @patch('scrapy_crawlera.middleware.logging')
    def test_open_spider_logging(self, mock_logger):
        spider = self.spider
        self.spider.crawlera_enabled = True
        crawler = self._mock_crawler(spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        expected_calls = [
            call(
                "Using crawlera at %s (apikey: %s)" % (
                    self.mwcls.url, 'apikey'
                ),
                extra={'spider': spider},
            ),
            call(
                "CrawleraMiddleware: disabling download delays on Scrapy side to optimize delays introduced by Crawlera. "
                "To avoid this behaviour you can use the CRAWLERA_PRESERVE_DELAY setting but keep in mind that this may slow down the crawl significantly",
                extra={'spider': spider},
            ),
        ]
        assert mock_logger.info.call_args_list == expected_calls
