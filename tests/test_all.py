import binascii
import os
from copy import copy
from random import choice
from unittest import TestCase

import pytest

try:
    from unittest.mock import call, patch  # type: ignore
except ImportError:
    from mock import call, patch  # type: ignore

from scrapy.downloadermiddlewares.httpproxy import HttpProxyMiddleware
from scrapy.exceptions import ScrapyDeprecationWarning
from scrapy.http import Request, Response
from scrapy.resolver import dnscache
from scrapy.spiders import Spider
from scrapy.utils.test import get_crawler
from twisted.internet.error import ConnectionDone, ConnectionRefusedError
from w3lib.http import basic_auth_header

from scrapy_zyte_smartproxy import ZyteSmartProxyMiddleware, __version__

RESPONSE_IDENTIFYING_HEADERS = (
    ("X-Crawlera-Version", None),
    ("X-Crawlera-Version", ""),
    ("X-Crawlera-Version", "1.36.3-cd5e44"),
    ("Zyte-Request-Id", "123456789"),
    ("zyte-error-type", "foo"),
)


class MockedSlot(object):

    def __init__(self, delay=0.0):
        self.delay = delay


class ZyteSmartProxyMiddlewareTestCase(TestCase):

    mwcls = ZyteSmartProxyMiddleware
    bancode = 503
    auth_error_code = 407

    def setUp(self):
        self.spider = Spider("foo")
        self.settings = {"ZYTE_SMARTPROXY_APIKEY": "apikey"}
        Response_init_orig = Response.__init__

        def Response_init_new(self, *args, **kwargs):
            assert not kwargs.get(
                "request"
            ), "response objects at this stage shall not be pinned"
            return Response_init_orig(self, *args, **kwargs)

        Response.__init__ = Response_init_new

    def _mock_zyte_smartproxy_response(self, url, headers=None, **kwargs):
        headers = headers or {}
        k, v = choice(RESPONSE_IDENTIFYING_HEADERS)
        headers[k] = v
        return Response(url, headers=headers, **kwargs)

    def _mock_crawler(self, spider, settings=None):

        class MockedDownloader(object):
            slots = {}

        class MockedEngine(object):
            downloader = MockedDownloader()
            fake_spider_closed_result = None

            def close_spider(self, spider, reason):
                self.fake_spider_closed_result = (spider, reason)

        # with `spider` instead of `type(spider)` raises an exception
        crawler = get_crawler(type(spider), settings)
        crawler.engine = MockedEngine()
        return crawler

    def _assert_disabled(self, spider, settings=None):
        crawler = self._mock_crawler(spider, settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        req = Request("http://example.com")
        out = mw.process_request(req, spider)
        self.assertEqual(out, None)
        self.assertEqual(req.meta.get("proxy"), None)
        self.assertEqual(req.meta.get("download_timeout"), None)
        self.assertEqual(req.headers.get("Proxy-Authorization"), None)
        res = Response(req.url)
        assert mw.process_response(req, res, spider) is res
        res = Response(req.url, status=mw.ban_code)
        assert mw.process_response(req, res, spider) is res

    def _assert_enabled(
        self,
        spider,
        settings=None,
        proxyurl="http://proxy.zyte.com:8011",
        proxyurlcreds="http://apikey:@proxy.zyte.com:8011",
        proxyauth=basic_auth_header("apikey", ""),
        maxbans=400,
        download_timeout=190,
    ):
        crawler = self._mock_crawler(spider, settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        httpproxy = HttpProxyMiddleware.from_crawler(crawler)
        assert mw.url == proxyurl
        req = Request("http://example.com")
        assert mw.process_request(req, spider) is None
        self.assertEqual(req.meta.get("proxy"), proxyurlcreds)
        self.assertEqual(req.meta.get("download_timeout"), download_timeout)
        self.assertNotIn(b"Proxy-Authorization", req.headers)

        res = self._mock_zyte_smartproxy_response(req.url)
        assert mw.process_response(req, res, spider) is res

        # disabled if 'dont_proxy=True' is set
        req = Request("http://example.com")
        req.meta["dont_proxy"] = True
        assert mw.process_request(req, spider) is None
        assert httpproxy.process_request(req, spider) is None
        self.assertEqual(req.meta.get("proxy"), None)
        self.assertEqual(req.meta.get("download_timeout"), None)
        self.assertNotIn(b"Proxy-Authorization", req.headers)
        res = self._mock_zyte_smartproxy_response(req.url)
        assert mw.process_response(req, res, spider) is res

        del req.meta["dont_proxy"]
        assert mw.process_request(req, spider) is None
        assert httpproxy.process_request(req, spider) is None
        self.assertEqual(req.meta.get("proxy"), proxyurl)
        self.assertEqual(req.meta.get("download_timeout"), download_timeout)
        self.assertEqual(req.headers.get("Proxy-Authorization"), proxyauth)

        if maxbans > 0:
            # assert ban count is reseted after a succesful response
            res = self._mock_zyte_smartproxy_response(
                "http://banned.example", status=self.bancode
            )
            assert mw.process_response(req, res, spider) is res
            self.assertEqual(crawler.engine.fake_spider_closed_result, None)
            res = self._mock_zyte_smartproxy_response("http://unbanned.example")
            assert mw.process_response(req, res, spider) is res
            self.assertEqual(crawler.engine.fake_spider_closed_result, None)
            self.assertEqual(mw._bans[None], 0)

        # check for not banning before maxbans for bancode
        for x in range(maxbans + 1):
            self.assertEqual(crawler.engine.fake_spider_closed_result, None)
            res = self._mock_zyte_smartproxy_response(
                "http://banned.example/%d" % x,
                status=self.bancode,
                headers={"X-Crawlera-Error": "banned"},
            )
            assert mw.process_response(req, res, spider) is res
            assert res.headers["X-Crawlera-Error"] == b"banned"
            assert res.headers["Zyte-Error"] == b"banned"

        # max bans reached and close_spider called
        self.assertEqual(crawler.engine.fake_spider_closed_result, (spider, "banned"))

    def test_disabled_by_lack_of_zyte_smartproxy_settings(self):
        self._assert_disabled(self.spider, settings={})

    def test_spider_zyte_smartproxy_enabled(self):
        self.assertFalse(hasattr(self.spider, "zyte_smartproxy_enabled"))
        self._assert_disabled(self.spider, self.settings)
        self.spider.zyte_smartproxy_enabled = True
        self._assert_enabled(self.spider, self.settings)
        self.spider.zyte_smartproxy_enabled = False
        self._assert_disabled(self.spider, self.settings)

    def test_enabled(self):
        self._assert_disabled(self.spider, self.settings)
        self.settings["ZYTE_SMARTPROXY_ENABLED"] = True
        self._assert_enabled(self.spider, self.settings)

    def test_spider_zyte_smartproxy_enabled_priority(self):
        self.spider.zyte_smartproxy_enabled = False
        self.settings["ZYTE_SMARTPROXY_ENABLED"] = True
        self._assert_disabled(self.spider, self.settings)

        self.spider.zyte_smartproxy_enabled = True
        self.settings["ZYTE_SMARTPROXY_ENABLED"] = False
        self._assert_enabled(self.spider, self.settings)

        self.spider.zyte_smartproxy_enabled = True
        self.settings["ZYTE_SMARTPROXY_ENABLED"] = True
        self._assert_enabled(self.spider, self.settings)

        self.spider.zyte_smartproxy_enabled = False
        self.settings["ZYTE_SMARTPROXY_ENABLED"] = False
        self._assert_disabled(self.spider, self.settings)

    def test_apikey(self):
        self.spider.zyte_smartproxy_enabled = True
        self.settings["ZYTE_SMARTPROXY_APIKEY"] = apikey = "apikey"
        proxyauth = basic_auth_header(apikey, "")
        self._assert_enabled(
            self.spider,
            self.settings,
            proxyauth=proxyauth,
            proxyurlcreds="http://apikey:@proxy.zyte.com:8011",
        )

        apikey = "notfromsettings"
        proxyauth = basic_auth_header(apikey, "")
        self.spider.zyte_smartproxy_apikey = apikey
        self._assert_enabled(
            self.spider,
            self.settings,
            proxyauth=proxyauth,
            proxyurlcreds="http://notfromsettings:@proxy.zyte.com:8011",
        )

    def test_proxyurl(self):
        self.spider.zyte_smartproxy_enabled = True
        self.settings["ZYTE_SMARTPROXY_URL"] = "http://localhost:8011"
        self._assert_enabled(
            self.spider,
            self.settings,
            proxyurl="http://localhost:8011",
            proxyurlcreds="http://apikey:@localhost:8011",
        )

    def test_proxyurl_no_protocol(self):
        self.spider.zyte_smartproxy_enabled = True
        self.settings["ZYTE_SMARTPROXY_URL"] = "localhost:8011"
        self._assert_enabled(
            self.spider,
            self.settings,
            proxyurl="http://localhost:8011",
            proxyurlcreds="http://apikey:@localhost:8011",
        )

    def test_proxyurl_https(self):
        self.spider.zyte_smartproxy_enabled = True
        self.settings["ZYTE_SMARTPROXY_URL"] = "https://localhost:8011"
        self._assert_enabled(
            self.spider,
            self.settings,
            proxyurl="https://localhost:8011",
            proxyurlcreds="https://apikey:@localhost:8011",
        )

    def test_proxyurl_including_noconnect(self):
        self.spider.zyte_smartproxy_enabled = True
        self.settings["ZYTE_SMARTPROXY_URL"] = "http://localhost:8011?noconnect"
        self._assert_enabled(
            self.spider,
            self.settings,
            proxyurl="http://localhost:8011?noconnect",
            proxyurlcreds="http://apikey:@localhost:8011?noconnect",
        )

    def test_maxbans(self):
        self.spider.zyte_smartproxy_enabled = True
        self.settings["ZYTE_SMARTPROXY_MAXBANS"] = maxbans = 0
        self._assert_enabled(self.spider, self.settings, maxbans=maxbans)
        self.settings["ZYTE_SMARTPROXY_MAXBANS"] = maxbans = 100
        self._assert_enabled(self.spider, self.settings, maxbans=maxbans)
        # Assert setting is coerced into correct type
        self.settings["ZYTE_SMARTPROXY_MAXBANS"] = "123"
        self._assert_enabled(self.spider, self.settings, maxbans=123)
        self.spider.zyte_smartproxy_maxbans = 99
        self._assert_enabled(self.spider, self.settings, maxbans=99)

    def test_download_timeout(self):
        self.spider.zyte_smartproxy_enabled = True
        self.settings["ZYTE_SMARTPROXY_DOWNLOAD_TIMEOUT"] = 60
        self._assert_enabled(self.spider, self.settings, download_timeout=60)
        # Assert setting is coerced into correct type
        self.settings["ZYTE_SMARTPROXY_DOWNLOAD_TIMEOUT"] = "42"
        self._assert_enabled(self.spider, self.settings, download_timeout=42)
        self.spider.zyte_smartproxy_download_timeout = 120
        self._assert_enabled(self.spider, self.settings, download_timeout=120)

    def test_hooks(self):
        proxyauth = basic_auth_header("foo", "")

        class _ECLS(self.mwcls):
            def is_enabled(self, spider):
                wascalled.append("is_enabled")
                return enabled

            def get_proxyauth(self, spider):
                wascalled.append("get_proxyauth")
                return proxyauth

        wascalled = []
        self.mwcls = _ECLS

        # test is_enabled returns False
        enabled = False
        self.spider.zyte_smartproxy_enabled = True
        self._assert_disabled(self.spider, self.settings)
        self.assertEqual(wascalled, ["is_enabled"])

        wascalled[:] = []  # reset
        enabled = True
        self.spider.zyte_smartproxy_enabled = False
        self._assert_enabled(
            self.spider,
            self.settings,
            proxyauth=proxyauth,
            proxyurlcreds="http://foo:@proxy.zyte.com:8011",
        )
        self.assertEqual(wascalled, ["is_enabled", "get_proxyauth"])

    def test_delay_adjustment(self):
        delay = 0.5
        slot_key = "example.com"
        url = "http://example.com"
        ban_url = "http://banned.example"

        self.spider.zyte_smartproxy_enabled = True

        crawler = self._mock_crawler(self.spider, self.settings)
        # ignore spider delay by default
        self.spider.download_delay = delay
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        httpproxy = HttpProxyMiddleware.from_crawler(crawler)
        self.assertEqual(self.spider.download_delay, 0)

        # preserve original delay
        self.spider.download_delay = delay
        self.spider.zyte_smartproxy_preserve_delay = True
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        self.assertEqual(self.spider.download_delay, delay)

        slot = MockedSlot(self.spider.download_delay)
        crawler.engine.downloader.slots[slot_key] = slot

        # ban without retry-after
        req = Request(url, meta={"download_slot": slot_key})
        assert mw.process_request(req, self.spider) is None
        assert httpproxy.process_request(req, self.spider) is None
        headers = {"X-Crawlera-Error": "banned"}
        res = self._mock_zyte_smartproxy_response(
            ban_url,
            status=self.bancode,
            headers=headers,
        )
        mw.process_response(req, res, self.spider)
        self.assertEqual(slot.delay, delay)
        self.assertEqual(self.spider.download_delay, delay)

        # ban with retry-after
        retry_after = 1.5
        headers = {"retry-after": str(retry_after), "X-Crawlera-Error": "banned"}
        res = self._mock_zyte_smartproxy_response(
            ban_url,
            status=self.bancode,
            headers=headers,
        )
        mw.process_response(req, res, self.spider)
        self.assertEqual(slot.delay, retry_after)
        self.assertEqual(self.spider.download_delay, delay)

        # DNS cache should be cleared in case of errors
        dnscache["proxy.zyte.com"] = "1.1.1.1"

        res = self._mock_zyte_smartproxy_response(url)
        mw.process_response(req, res, self.spider)
        self.assertEqual(slot.delay, delay)
        self.assertEqual(self.spider.download_delay, delay)
        self.assertIn("proxy.zyte.com", dnscache)

        # server failures
        mw.process_exception(req, ConnectionRefusedError(), self.spider)
        self.assertEqual(slot.delay, mw.connection_refused_delay)
        self.assertEqual(self.spider.download_delay, delay)
        self.assertNotIn("proxy.zyte.com", dnscache)

        dnscache["proxy.zyte.com"] = "1.1.1.1"
        res = self._mock_zyte_smartproxy_response(ban_url)
        mw.process_response(req, res, self.spider)
        self.assertEqual(slot.delay, delay)
        self.assertEqual(self.spider.download_delay, delay)
        self.assertIn("proxy.zyte.com", dnscache)

        mw.process_exception(req, ConnectionRefusedError(), self.spider)
        self.assertEqual(slot.delay, mw.connection_refused_delay)
        self.assertEqual(self.spider.download_delay, delay)
        self.assertNotIn("proxy.zyte.com", dnscache)

        dnscache["proxy.zyte.com"] = "1.1.1.1"
        res = self._mock_zyte_smartproxy_response(ban_url, status=self.bancode)
        mw.process_response(req, res, self.spider)
        self.assertEqual(slot.delay, delay)
        self.assertEqual(self.spider.download_delay, delay)
        self.assertIn("proxy.zyte.com", dnscache)

        mw.process_exception(req, ConnectionDone(), self.spider)
        self.assertEqual(slot.delay, mw.connection_refused_delay)
        self.assertEqual(self.spider.download_delay, delay)
        self.assertNotIn("proxy.zyte.com", dnscache)

    def test_process_exception_outside_zyte_smartproxy(self):
        self.spider.zyte_smartproxy_enabled = False
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)

        req = Request("https://scrapy.org")
        assert mw.process_exception(req, ConnectionDone(), self.spider) is None

    def test_jobid_header(self):
        # test without the environment variable 'SCRAPY_JOB'
        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        mw1 = self.mwcls.from_crawler(crawler)
        mw1.open_spider(self.spider)
        req1 = Request("http://example.com")
        self.assertEqual(mw1.process_request(req1, self.spider), None)
        self.assertEqual(req1.headers.get("X-Crawlera-Jobid"), None)
        self.assertEqual(req1.headers.get("Zyte-JobId"), None)

        # test with the environment variable 'SCRAPY_JOB'
        os.environ["SCRAPY_JOB"] = "2816"
        self.spider.zyte_smartproxy_enabled = True
        mw2 = self.mwcls.from_crawler(crawler)
        mw2.open_spider(self.spider)
        req2 = Request("http://example.com")
        self.assertEqual(mw2.process_request(req2, self.spider), None)
        self.assertEqual(req2.headers.get("X-Crawlera-Jobid"), b"2816")
        self.assertEqual(req2.headers.get("Zyte-JobId"), None)

        # Zyte API
        mw3 = self.mwcls.from_crawler(crawler)
        mw3.open_spider(self.spider)
        req3 = Request(
            "http://example.com",
            meta={
                "proxy": "http://apikey:@api.zyte.com:8011",
            },
        )
        self.assertEqual(mw3.process_request(req3, self.spider), None)
        self.assertEqual(req3.headers.get("X-Crawlera-Jobid"), None)
        self.assertEqual(req3.headers.get("Zyte-JobId"), b"2816")

    def _test_stats(self, settings, prefix):
        self.spider.zyte_smartproxy_enabled = True
        spider = self.spider
        settings = copy(settings)
        settings["ZYTE_SMARTPROXY_FORCE_ENABLE_ON_HTTP_CODES"] = [555]
        crawler = self._mock_crawler(spider, settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        httpproxy = HttpProxyMiddleware.from_crawler(crawler)

        req = Request("http://example.com")
        assert mw.process_request(req, spider) is None
        assert httpproxy.process_request(req, spider) is None
        self.assertEqual(crawler.stats.get_value("{}/request".format(prefix)), 1)
        self.assertEqual(
            crawler.stats.get_value("{}/request/method/GET".format(prefix)), 1
        )

        res = self._mock_zyte_smartproxy_response(req.url)
        assert mw.process_response(req, res, spider) is res
        self.assertEqual(crawler.stats.get_value("{}/response".format(prefix)), 1)
        self.assertEqual(
            crawler.stats.get_value("{}/response/status/200".format(prefix)), 1
        )

        req = Request("http://example.com/other", method="POST")
        assert mw.process_request(req, spider) is None
        assert httpproxy.process_request(req, spider) is None
        self.assertEqual(crawler.stats.get_value("{}/request".format(prefix)), 2)
        self.assertEqual(
            crawler.stats.get_value("{}/request/method/POST".format(prefix)), 1
        )

        res = self._mock_zyte_smartproxy_response(
            req.url, status=mw.ban_code, headers={"Zyte-Error": "somethingbad"}
        )
        assert mw.process_response(req, res, spider) is res
        self.assertEqual(crawler.stats.get_value("{}/response".format(prefix)), 2)
        self.assertEqual(
            crawler.stats.get_value(
                "{}/response/status/{}".format(prefix, mw.ban_code)
            ),
            1,
        )
        self.assertEqual(crawler.stats.get_value("{}/response/error".format(prefix)), 1)
        self.assertEqual(
            crawler.stats.get_value("{}/response/error/somethingbad".format(prefix)), 1
        )
        self.assertEqual(res.headers["X-Crawlera-Error"], b"somethingbad")
        self.assertEqual(res.headers["Zyte-Error"], b"somethingbad")

        res = self._mock_zyte_smartproxy_response(
            req.url,
            status=mw.ban_code,
            headers={"X-Crawlera-Error": "banned", "Retry-After": "1"},
        )
        assert mw.process_response(req, res, spider) is res
        self.assertEqual(crawler.stats.get_value("{}/response".format(prefix)), 3)
        self.assertEqual(
            crawler.stats.get_value(
                "{}/response/status/{}".format(prefix, mw.ban_code)
            ),
            2,
        )
        self.assertEqual(
            crawler.stats.get_value("{}/response/banned".format(prefix)), 1
        )
        self.assertEqual(res.headers["X-Crawlera-Error"], b"banned")
        self.assertEqual(res.headers["Zyte-Error"], b"banned")

        res = self._mock_zyte_smartproxy_response(
            req.url,
            status=mw.ban_code,
            headers={"X-Crawlera-Error": "banned", "Retry-After": "1"},
        )
        slot_key = "example.com"
        crawler.engine.downloader.slots[slot_key] = MockedSlot()
        req.meta["download_slot"] = "example.com"
        assert mw.process_response(req, res, spider) is res
        del req.meta["download_slot"]
        self.assertEqual(crawler.stats.get_value("{}/delay/banned".format(prefix)), 1)
        self.assertEqual(
            crawler.stats.get_value("{}/delay/banned/total".format(prefix)), 1
        )

        res = self._mock_zyte_smartproxy_response(
            req.url,
            status=407,
            headers={"X-Crawlera-Error": "bad_proxy_auth"},
        )
        assert isinstance(mw.process_response(req, res, spider), Request)
        self.assertEqual(crawler.stats.get_value("{}/retries/auth".format(prefix)), 1)

        res = self._mock_zyte_smartproxy_response(
            req.url,
            status=407,
            headers={"X-Crawlera-Error": "bad_proxy_auth"},
        )
        req.meta["zyte_smartproxy_auth_retry_times"] = 11
        assert mw.process_response(req, res, spider) is res
        del req.meta["zyte_smartproxy_auth_retry_times"]
        self.assertEqual(crawler.stats.get_value("{}/retries/auth".format(prefix)), 1)
        self.assertEqual(
            crawler.stats.get_value("{}/retries/auth/max_reached".format(prefix)), 1
        )

        res = self._mock_zyte_smartproxy_response(
            req.url,
            status=555,
        )
        req.meta["dont_proxy"] = True
        assert isinstance(mw.process_response(req, res, spider), Request)
        del req.meta["dont_proxy"]
        self.assertEqual(
            crawler.stats.get_value(
                "{}/retries/should_have_been_enabled".format(prefix)
            ),
            1,
        )

    def test_stats_spm(self):
        self._test_stats(self.settings, "zyte_smartproxy")

    def test_stats_zapi(self):
        settings = copy(self.settings)
        settings["ZYTE_SMARTPROXY_URL"] = "http://api.zyte.com:8011"
        self._test_stats(settings, "zyte_api_proxy")

    def _make_fake_request(self, spider, zyte_smartproxy_enabled, **kwargs):
        spider.zyte_smartproxy_enabled = zyte_smartproxy_enabled
        crawler = self._mock_crawler(spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        httpproxy = HttpProxyMiddleware.from_crawler(crawler)
        headers = {
            "X-Crawlera-Debug": True,
            "X-Crawlera-Foo": "foo",
            "X-Crawlera-Profile": "desktop",
            "User-Agent": "Scrapy",
            "": None,
            "Zyte-Bar": "bar",
            "Zyte-BrowserHtml": True,
            "Zyte-Geolocation": "foo",
        }
        req = Request("http://example.com", headers=headers, **kwargs)
        mw.process_request(req, spider)
        httpproxy.process_request(req, spider)
        return req

    def test_clean_headers_when_disabled(self):
        req = self._make_fake_request(self.spider, zyte_smartproxy_enabled=False)

        self.assertNotIn(b"X-Crawlera-Debug", req.headers)
        self.assertNotIn(b"X-Crawlera-Foo", req.headers)
        self.assertNotIn(b"X-Crawlera-Profile", req.headers)
        self.assertNotIn(b"Zyte-Bar", req.headers)
        self.assertNotIn(b"Zyte-BrowserHtml", req.headers)
        self.assertNotIn(b"Zyte-Geolocation", req.headers)
        self.assertIn(b"User-Agent", req.headers)

    def test_clean_headers_when_enabled_spm(self):
        req = self._make_fake_request(self.spider, zyte_smartproxy_enabled=True)
        self.assertEqual(req.headers[b"X-Crawlera-Debug"], b"True")
        self.assertEqual(req.headers[b"X-Crawlera-Foo"], b"foo")
        self.assertEqual(req.headers[b"X-Crawlera-Profile"], b"desktop")
        self.assertNotIn(b"Zyte-Bar", req.headers)
        self.assertNotIn(b"Zyte-BrowserHtml", req.headers)
        self.assertNotIn(b"Zyte-Geolocation", req.headers)
        self.assertEqual(req.headers[b"X-Crawlera-Region"], b"foo")
        self.assertIn(b"User-Agent", req.headers)

    def test_clean_headers_when_enabled_zyte_api(self):
        meta = {"proxy": "http://apikey:@api.zyte.com:8011"}
        req = self._make_fake_request(
            self.spider, zyte_smartproxy_enabled=True, meta=meta
        )
        self.assertNotIn(b"X-Crawlera-Debug", req.headers)
        self.assertNotIn(b"X-Crawlera-Foo", req.headers)
        self.assertNotIn(b"X-Crawlera-Profile", req.headers)
        self.assertEqual(req.headers[b"Zyte-Bar"], b"bar")
        self.assertEqual(req.headers[b"Zyte-BrowserHtml"], b"True")
        self.assertEqual(req.headers[b"Zyte-Device"], b"desktop")
        self.assertEqual(req.headers[b"Zyte-Geolocation"], b"foo")
        self.assertIn(b"User-Agent", req.headers)

    def test_zyte_smartproxy_default_headers(self):
        spider = self.spider
        self.spider.zyte_smartproxy_enabled = True

        self.settings["ZYTE_SMARTPROXY_DEFAULT_HEADERS"] = {
            "X-Crawlera-Profile": "desktop",
        }
        crawler = self._mock_crawler(spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        req = Request("http://example.com/other")
        assert mw.process_request(req, spider) is None
        self.assertEqual(req.headers["X-Crawlera-Profile"], b"desktop")
        self.assertNotIn("Zyte-Device", req.headers)

        # Header translation
        req = Request(
            "http://example.com/other",
            meta={"proxy": "http://apikey:@api.zyte.com:8011"},
        )
        assert mw.process_request(req, spider) is None
        self.assertNotIn("X-Crawlera-Profile", req.headers)
        self.assertEqual(req.headers["Zyte-Device"], b"desktop")

        # test ignore None headers
        self.settings["ZYTE_SMARTPROXY_DEFAULT_HEADERS"] = {
            "X-Crawlera-Profile": None,
            "X-Crawlera-Cookies": "disable",
        }
        crawler = self._mock_crawler(spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        req = Request("http://example.com/other")
        assert mw.process_request(req, spider) is None
        self.assertEqual(req.headers["X-Crawlera-Cookies"], b"disable")
        self.assertNotIn("X-Crawlera-Profile", req.headers)

    @patch("scrapy_zyte_smartproxy.middleware.warnings")
    @patch("scrapy_zyte_smartproxy.middleware.logger")
    def test_zyte_smartproxy_default_headers_conflicting_headers(
        self, mock_logger, mock_warnings
    ):
        spider = self.spider
        self.spider.zyte_smartproxy_enabled = True

        self.settings["ZYTE_SMARTPROXY_DEFAULT_HEADERS"] = {
            "X-Crawlera-Profile": "desktop",
        }
        crawler = self._mock_crawler(spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)

        req = Request("http://example.com/other", headers={"X-Crawlera-UA": "desktop"})
        assert mw.process_request(req, spider) is None
        self.assertEqual(req.headers["X-Crawlera-UA"], b"desktop")
        self.assertEqual(req.headers["X-Crawlera-Profile"], b"desktop")
        some_requests_warning = (
            "The headers ('X-Crawlera-Profile', 'X-Crawlera-UA') are "
            "conflicting on some of your requests. Please check "
            "https://docs.zyte.com/smart-proxy-manager.html#request-headers "
            "for more information. You can set LOG_LEVEL=DEBUG to see the "
            "urls with problems."
        )
        mock_warnings.warn.assert_called_with(some_requests_warning)
        other_request_warning = (
            "The headers ('X-Crawlera-Profile', 'X-Crawlera-UA') are "
            "conflicting on request http://example.com/other. "
            "X-Crawlera-UA will be ignored. Please check "
            "https://docs.zyte.com/smart-proxy-manager.html#request-headers "
            "for more information"
        )
        mock_logger.debug.assert_called_with(
            other_request_warning, extra={"spider": spider}
        )

        # test it ignores case
        req = Request("http://example.com/other", headers={"x-crawlera-ua": "desktop"})
        assert mw.process_request(req, spider) is None
        self.assertEqual(req.headers["X-Crawlera-UA"], b"desktop")
        self.assertEqual(req.headers["X-Crawlera-Profile"], b"desktop")
        mock_warnings.warn.assert_called_with(some_requests_warning)
        mock_logger.debug.assert_called_with(
            other_request_warning, extra={"spider": spider}
        )

    def test_dont_proxy_false_does_nothing(self):
        spider = self.spider
        spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        req = Request("http://example.com/other")
        req.meta["dont_proxy"] = False
        assert mw.process_request(req, spider) is None
        self.assertIsNotNone(req.meta.get("proxy"))

    def test_is_banned(self):
        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        req = self._make_fake_request(self.spider, zyte_smartproxy_enabled=True)

        res = Response(req.url, status=200)
        res = mw.process_response(req, res, self.spider)
        self.assertFalse(mw._is_banned(res))
        res = Response(req.url, status=503, headers={"X-Crawlera-Error": "noslaves"})
        res = mw.process_response(req, res, self.spider)
        self.assertFalse(mw._is_banned(res))
        res = Response(
            req.url,
            status=503,
            headers={"Zyte-Error": "/limits/over-global-limit"},
        )
        res = mw.process_response(req, res, self.spider)
        self.assertFalse(mw._is_banned(res))

        res = Response(req.url, status=503, headers={"X-Crawlera-Error": "banned"})
        res = mw.process_response(req, res, self.spider)
        self.assertTrue(mw._is_banned(res))
        res = Response(
            req.url, status=520, headers={"Zyte-Error": "/download/temporary-error"}
        )
        res = mw.process_response(req, res, self.spider)
        self.assertTrue(mw._is_banned(res))
        res = Response(
            req.url,
            status=521,
            headers={"Zyte-Error": "/download/internal-error"},
        )
        res = mw.process_response(req, res, self.spider)
        self.assertTrue(mw._is_banned(res))

    @patch("random.uniform")
    def test_noslaves_delays(self, random_uniform_patch):
        # mock random.uniform to just return the max delay
        random_uniform_patch.side_effect = lambda x, y: y

        slot_key = "example.com"
        url = "http://example.com"
        ban_url = "http://banned.example"
        max_delay = 70
        backoff_step = 15
        default_delay = 0

        self.settings["ZYTE_SMARTPROXY_BACKOFF_STEP"] = backoff_step
        self.settings["ZYTE_SMARTPROXY_BACKOFF_MAX"] = max_delay

        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        httpproxy = HttpProxyMiddleware.from_crawler(crawler)

        slot = MockedSlot()
        crawler.engine.downloader.slots[slot_key] = slot

        noslaves_req = Request(url, meta={"download_slot": slot_key})
        assert mw.process_request(noslaves_req, self.spider) is None
        assert httpproxy.process_request(noslaves_req, self.spider) is None

        # delays grow exponentially with any throttling error
        noslaves_response = self._mock_zyte_smartproxy_response(
            ban_url,
            status=503,
            headers={"X-Crawlera-Error": "noslaves"},
        )
        mw.process_response(noslaves_req, noslaves_response, self.spider)
        self.assertEqual(slot.delay, backoff_step)

        over_use_limit_response = self._mock_zyte_smartproxy_response(
            ban_url,
            status=429,
            headers={"Zyte-Error": "/limits/over-user-limit"},
        )
        mw.process_response(noslaves_req, over_use_limit_response, self.spider)
        self.assertEqual(slot.delay, backoff_step * 2**1)

        over_domain_limit_response = self._mock_zyte_smartproxy_response(
            ban_url,
            status=429,
            headers={"Zyte-Error": "/limits/over-domain-limit"},
        )
        mw.process_response(noslaves_req, over_domain_limit_response, self.spider)
        self.assertEqual(slot.delay, backoff_step * 2**2)

        over_global_limit_response = self._mock_zyte_smartproxy_response(
            ban_url,
            status=503,
            headers={"Zyte-Error": "/limits/over-global-limit"},
        )
        mw.process_response(noslaves_req, over_global_limit_response, self.spider)
        self.assertEqual(slot.delay, max_delay)

        # other responses reset delay
        ban_req = Request(url, meta={"download_slot": slot_key})
        assert mw.process_request(ban_req, self.spider) is None
        assert httpproxy.process_request(ban_req, self.spider) is None
        ban_headers = {"X-Crawlera-Error": "banned"}
        ban_res = self._mock_zyte_smartproxy_response(
            ban_url,
            status=self.bancode,
            headers=ban_headers,
        )
        mw.process_response(ban_req, ban_res, self.spider)
        self.assertEqual(slot.delay, default_delay)

        mw.process_response(noslaves_req, noslaves_response, self.spider)
        self.assertEqual(slot.delay, backoff_step)

        good_req = Request(url, meta={"download_slot": slot_key})
        assert mw.process_request(good_req, self.spider) is None
        assert httpproxy.process_request(good_req, self.spider) is None
        good_res = self._mock_zyte_smartproxy_response(
            url,
            status=200,
        )
        mw.process_response(good_req, good_res, self.spider)
        self.assertEqual(slot.delay, default_delay)

    @patch("random.uniform")
    def test_auth_error_retries(self, random_uniform_patch):
        # mock random.uniform to just return the max delay
        random_uniform_patch.side_effect = lambda x, y: y

        slot_key = "example.com"
        url = "http://example.com"
        ban_url = "http://auth.error"
        max_delay = 70
        backoff_step = 15

        self.settings["ZYTE_SMARTPROXY_BACKOFF_STEP"] = backoff_step
        self.settings["ZYTE_SMARTPROXY_BACKOFF_MAX"] = max_delay

        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        mw.max_auth_retry_times = 4
        httpproxy = HttpProxyMiddleware.from_crawler(crawler)

        slot = MockedSlot()
        crawler.engine.downloader.slots[slot_key] = slot

        auth_error_req = Request(url, meta={"download_slot": slot_key})
        assert mw.process_request(auth_error_req, self.spider) is None
        assert httpproxy.process_request(auth_error_req, self.spider) is None
        auth_error_headers = {"X-Crawlera-Error": "bad_proxy_auth"}
        auth_error_response = self._mock_zyte_smartproxy_response(
            ban_url, status=self.auth_error_code, headers=auth_error_headers
        )

        # delays grow exponentially, retry times increase accordingly
        req = mw.process_response(auth_error_req, auth_error_response, self.spider)
        self.assertEqual(slot.delay, backoff_step)
        retry_times = req.meta["zyte_smartproxy_auth_retry_times"]
        self.assertEqual(retry_times, 1)

        auth_error_req.meta["zyte_smartproxy_auth_retry_times"] = retry_times
        req = mw.process_response(auth_error_req, auth_error_response, self.spider)
        self.assertEqual(slot.delay, backoff_step * 2**1)
        retry_times = req.meta["zyte_smartproxy_auth_retry_times"]
        self.assertEqual(retry_times, 2)

        auth_error_req.meta["zyte_smartproxy_auth_retry_times"] = retry_times
        req = mw.process_response(auth_error_req, auth_error_response, self.spider)
        self.assertEqual(slot.delay, backoff_step * 2**2)
        retry_times = req.meta["zyte_smartproxy_auth_retry_times"]
        self.assertEqual(retry_times, 3)

        auth_error_req.meta["zyte_smartproxy_auth_retry_times"] = retry_times
        req = mw.process_response(auth_error_req, auth_error_response, self.spider)
        self.assertEqual(slot.delay, max_delay)
        retry_times = req.meta["zyte_smartproxy_auth_retry_times"]
        self.assertEqual(retry_times, 4)

        # Should return a response when after max number of retries
        auth_error_req.meta["zyte_smartproxy_auth_retry_times"] = retry_times
        res = mw.process_response(auth_error_req, auth_error_response, self.spider)
        self.assertIsInstance(res, Response)

        # A 407 response not coming directly from Zyte Smart Proxy Manager is
        # not retried
        non_zyte_smartproxy_407_response = self._mock_zyte_smartproxy_response(
            ban_url,
            status=self.auth_error_code,
        )
        res = mw.process_response(
            auth_error_req, non_zyte_smartproxy_407_response, self.spider
        )
        self.assertIsInstance(res, Response)

    @patch("scrapy_zyte_smartproxy.middleware.logger")
    def test_open_spider_logging(self, mock_logger):
        spider = self.spider
        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        expected_calls = [
            call(
                "Using Zyte proxy service %s with an API key ending in %s"
                % (self.mwcls.url, "apikey"),
                extra={"spider": spider},
            ),
            call(
                "ZyteSmartProxyMiddleware: disabling download delays in "
                "Scrapy to optimize delays introduced by Zyte proxy services. "
                "To avoid this behaviour you can use the "
                "ZYTE_SMARTPROXY_PRESERVE_DELAY setting, but keep in mind "
                "that this may slow down the crawl significantly",
                extra={"spider": spider},
            ),
        ]
        assert mock_logger.info.call_args_list == expected_calls

    def test_process_response_enables_zyte_smartproxy(self):
        url = "https://scrapy.org"

        self.spider.zyte_smartproxy_enabled = False
        self.settings["ZYTE_SMARTPROXY_FORCE_ENABLE_ON_HTTP_CODES"] = [403]
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)

        # A good code response should not enable it
        req = Request(url)
        res = Response(url, status=200)
        mw.process_request(req, self.spider)
        out = mw.process_response(req, res, self.spider)
        self.assertIsInstance(out, Response)
        self.assertEqual(mw.enabled_for_domain, {})
        self.assertEqual(mw.enabled, False)
        self.assertEqual(mw.crawler.stats.get_stats(), {})

        # A bad code response should enable it
        res = Response(url, status=403)
        mw.process_request(req, self.spider)
        out = mw.process_response(req, res, self.spider)
        self.assertIsInstance(out, Request)
        self.assertEqual(mw.enabled, False)
        self.assertEqual(mw.enabled_for_domain["scrapy.org"], True)
        self.assertEqual(
            mw.crawler.stats.get_stats(),
            {
                "zyte_smartproxy/retries/should_have_been_enabled": 1,
            },
        )

        # Another regular response with bad code should be done on Zyte Smart
        # Proxy Manager and not be retried
        res = Response(url, status=403)
        mw.process_request(req, self.spider)
        out = mw.process_response(req, res, self.spider)
        self.assertIsInstance(out, Response)
        self.assertEqual(mw.enabled, False)
        self.assertEqual(mw.enabled_for_domain["scrapy.org"], True)
        self.assertEqual(mw.crawler.stats.get_value("zyte_smartproxy/request"), 1)

        # A Zyte Smart Proxy Manager response with bad code should not be
        # retried as well
        mw.process_request(req, self.spider)
        res = self._mock_zyte_smartproxy_response(url, status=403)
        out = mw.process_response(req, res, self.spider)
        self.assertIsInstance(out, Response)
        self.assertEqual(mw.enabled, False)
        self.assertEqual(mw.enabled_for_domain["scrapy.org"], True)
        self.assertEqual(mw.crawler.stats.get_value("zyte_smartproxy/request"), 2)

    def test_process_response_from_file_scheme(self):
        url = "file:///tmp/foobar.txt"

        self.spider.zyte_smartproxy_enabled = False
        self.settings["ZYTE_SMARTPROXY_FORCE_ENABLE_ON_HTTP_CODES"] = [403]
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.enabled_for_domain = {}
        mw.open_spider(self.spider)

        # A good code response should not enable it
        req = Request(url)
        res = Response(url, status=200)
        mw.process_request(req, self.spider)
        out = mw.process_response(req, res, self.spider)
        self.assertIsInstance(out, Response)
        self.assertEqual(mw.enabled_for_domain, {})
        self.assertEqual(mw.enabled, False)
        self.assertEqual(mw.crawler.stats.get_stats(), {})
        self.assertEqual(out.status, 200)

    @patch("scrapy_zyte_smartproxy.middleware.logger")
    def test_apikey_warning_zyte_smartproxy_disabled(self, mock_logger):
        self.spider.zyte_smartproxy_enabled = False
        settings = {}
        crawler = self._mock_crawler(self.spider, settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        self.assertFalse(mw.enabled)
        mock_logger.warning.assert_not_called()

    @patch("scrapy_zyte_smartproxy.middleware.logger")
    def test_no_apikey_warning_zyte_smartproxy_enabled(self, mock_logger):
        self.spider.zyte_smartproxy_enabled = True
        settings = {}
        crawler = self._mock_crawler(self.spider, settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        self.assertTrue(mw.enabled)
        mock_logger.warning.assert_called_with(
            "Zyte proxy services cannot be used without an API key",
            extra={"spider": self.spider},
        )

    @patch("scrapy_zyte_smartproxy.middleware.logger")
    def test_no_apikey_warning_force_enable(self, mock_logger):
        self.spider.zyte_smartproxy_enabled = False
        settings = {"ZYTE_SMARTPROXY_FORCE_ENABLE_ON_HTTP_CODES": [403]}
        crawler = self._mock_crawler(self.spider, settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        self.assertFalse(mw.enabled)
        mock_logger.warning.assert_called_with(
            "Zyte proxy services cannot be used without an API key",
            extra={"spider": self.spider},
        )

    @patch("scrapy_zyte_smartproxy.middleware.logger")
    def test_apikey_warning_force_enable(self, mock_logger):
        self.spider.zyte_smartproxy_enabled = False
        settings = {
            "ZYTE_SMARTPROXY_FORCE_ENABLE_ON_HTTP_CODES": [403],
            "ZYTE_SMARTPROXY_APIKEY": "apikey",
        }
        crawler = self._mock_crawler(self.spider, settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        self.assertFalse(mw.enabled)
        mock_logger.warning.assert_not_called()

    def test_is_enabled_warnings(self):
        self._assert_disabled(self.spider, self.settings)
        self.settings["HUBPROXY_ENABLED"] = True
        with pytest.warns(ScrapyDeprecationWarning) as record:
            self._assert_enabled(self.spider, self.settings)
            assert len(record) == 1
            assert "HUBPROXY_ENABLED setting is deprecated" in str(record[0].message)

        del self.settings["HUBPROXY_ENABLED"]
        self.spider.use_hubproxy = False
        with pytest.warns(ScrapyDeprecationWarning) as record:
            self._assert_disabled(self.spider, self.settings)
            assert len(record) == 1
            assert "use_hubproxy attribute is deprecated" in str(record[0].message)

    def test_settings_warnings(self):
        self.spider.hubproxy_maxbans = 10
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        with pytest.warns(ScrapyDeprecationWarning) as record:
            mw.open_spider(self.spider)
            assert len(record) == 1
            assert "hubproxy_maxbans attribute is deprecated" in str(record[0].message)
        del self.spider.hubproxy_maxbans

        self.settings["HUBPROXY_BACKOFF_MAX"] = 10
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        with pytest.warns(ScrapyDeprecationWarning) as record:
            mw.open_spider(self.spider)
            assert len(record) == 1
            assert "HUBPROXY_BACKOFF_MAX setting is deprecated" in str(
                record[0].message
            )

    def test_no_slot(self):
        url = "http://example.com"
        ban_url = "http://banned.example"

        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)

        # there are no slot named 'example.com'
        noslaves_req = Request(url, meta={"download_slot": "example.com"})
        assert mw.process_request(noslaves_req, self.spider) is None

        headers = {"X-Crawlera-Error": "noslaves"}
        noslaves_res = self._mock_zyte_smartproxy_response(
            ban_url,
            status=self.bancode,
            headers=headers,
        )
        # checking that response was processed
        response = mw.process_response(noslaves_req, noslaves_res, self.spider)
        assert response.status == 503

    def test_settings_dict(self):
        self.spider.zyte_smartproxy_enabled = True
        self.settings["ZYTE_SMARTPROXY_DEFAULT_HEADERS"] = {
            "X-Crawlera-Profile": "desktop",
        }
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        # we don't have a dict settings yet, have to mess with protected
        # property
        mw._settings.append(("default_headers", dict))
        mw.open_spider(self.spider)
        req = Request("http://example.com/other")
        mw.process_request(req, self.spider)
        assert mw.process_request(req, self.spider) is None
        self.assertEqual(req.headers["X-Crawlera-Profile"], b"desktop")

    def test_client_header(self):
        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        req1 = Request("http://example.com")
        self.assertEqual(mw.process_request(req1, self.spider), None)
        client = "scrapy-zyte-smartproxy/{}".format(__version__).encode()
        self.assertEqual(req1.headers.get("X-Crawlera-Client"), client)
        self.assertEqual(req1.headers.get("Zyte-Client"), None)

        req2 = Request(
            "http://example.com",
            meta={
                "proxy": "http://apikey:@api.zyte.com:8011",
            },
        )
        self.assertEqual(mw.process_request(req2, self.spider), None)
        self.assertEqual(req2.headers.get("X-Crawlera-Client"), None)
        self.assertEqual(req2.headers.get("Zyte-Client"), client)

    def test_scrapy_httpproxy_integration(self):
        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        smartproxy = self.mwcls.from_crawler(crawler)
        smartproxy.open_spider(self.spider)
        httpproxy = HttpProxyMiddleware.from_crawler(crawler)
        request = Request("https://example.com")
        auth_header = basic_auth_header("apikey", "")

        # 1st pass
        self.assertEqual(smartproxy.process_request(request, self.spider), None)
        self.assertEqual(httpproxy.process_request(request, self.spider), None)
        self.assertEqual(request.meta["proxy"], "http://proxy.zyte.com:8011")
        self.assertEqual(request.headers[b"Proxy-Authorization"], auth_header)

        # 2nd pass (e.g. retry or redirect)
        self.assertEqual(smartproxy.process_request(request, self.spider), None)
        self.assertEqual(httpproxy.process_request(request, self.spider), None)
        self.assertEqual(request.meta["proxy"], "http://proxy.zyte.com:8011")
        self.assertEqual(request.headers[b"Proxy-Authorization"], auth_header)

    def test_subclass_non_basic_header(self):

        class Subclass(self.mwcls):
            def get_proxyauth(self, spider):
                return b"Non-Basic foo"

        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        smartproxy = Subclass.from_crawler(crawler)
        with pytest.raises(ValueError):
            smartproxy.open_spider(self.spider)

    def test_subclass_basic_header_non_base64(self):

        class Subclass(self.mwcls):
            def get_proxyauth(self, spider):
                return b"Basic foo"

        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        smartproxy = Subclass.from_crawler(crawler)
        with pytest.raises((TypeError, binascii.Error)):
            smartproxy.open_spider(self.spider)

    def test_subclass_basic_header_nonurlsafe_base64(self):

        class Subclass(self.mwcls):
            def get_proxyauth(self, spider):
                return b"Basic YWF+Og=="

        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        smartproxy = Subclass.from_crawler(crawler)
        smartproxy.open_spider(self.spider)
        self.assertEqual(smartproxy._auth_url, "http://aa~:@proxy.zyte.com:8011")

    def test_subclass_basic_header_urlsafe_base64(self):

        class Subclass(self.mwcls):
            def get_proxyauth(self, spider):
                return b"Basic YWF-Og=="

        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        smartproxy = Subclass.from_crawler(crawler)
        smartproxy.open_spider(self.spider)
        self.assertEqual(smartproxy._auth_url, "http://aa~:@proxy.zyte.com:8011")

    def test_header_translation(self):
        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        value = b"foo"

        zyte_api_to_spm_translations = {
            b"Zyte-Device": b"X-Crawlera-Profile",
            b"Zyte-Geolocation": b"X-Crawlera-Region",
            b"Zyte-JobId": b"X-Crawlera-JobId",
            b"Zyte-Override-Headers": b"X-Crawlera-Profile-Pass",
        }
        for header, translation in zyte_api_to_spm_translations.items():
            request = Request(
                "https://example.com",
                headers={header: value},
            )
            self.assertEqual(mw.process_request(request, self.spider), None)
            self.assertNotIn(header, request.headers)
            self.assertEqual(request.headers[translation], value)

        spm_to_zyte_api_translations = {
            v: k for k, v in zyte_api_to_spm_translations.items()
        }
        for header, translation in spm_to_zyte_api_translations.items():
            request = Request(
                "https://example.com",
                headers={header: value},
                meta={"proxy": "http://apikey:@api.zyte.com:8011"},
            )
            self.assertEqual(mw.process_request(request, self.spider), None)
            self.assertNotIn(header, request.headers)
            self.assertEqual(request.headers[translation], value)

    @patch("scrapy_zyte_smartproxy.middleware.logger")
    def test_header_drop_warnings(self, mock_logger):
        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)

        request = Request(
            "https://example.com",
            headers={"Zyte-Device": "desktop"},
        )
        self.assertEqual(mw.process_request(request, self.spider), None)
        mock_logger.warning.assert_called_with(
            "Translating (and dropping) header %r (%r) as %r on request %r",
            b"zyte-device",
            [b"desktop"],
            b"x-crawlera-profile",
            request,
        )
        mock_logger.warning.reset_mock()

        request = Request(
            "https://example.com",
            headers={"X-Crawlera-Profile": "desktop"},
            meta={"proxy": "http://apikey:@api.zyte.com:8011"},
        )
        self.assertEqual(mw.process_request(request, self.spider), None)
        mock_logger.warning.assert_called_with(
            "Translating (and dropping) header %r (%r) as %r on request %r",
            b"x-crawlera-profile",
            [b"desktop"],
            b"zyte-device",
            request,
        )
        mock_logger.warning.reset_mock()

        request = Request(
            "https://example.com",
            headers={"Zyte-Foo": "bar"},
        )
        self.assertEqual(mw.process_request(request, self.spider), None)
        mock_logger.warning.assert_called_with(
            (
                "Dropping header %r (%r) from request %r, as this "
                "request is proxied with %s and not with %s, and "
                "automatic translation is not supported for this "
                "header. See "
                "https://docs.zyte.com/zyte-api/migration/zyte/smartproxy.html"
                "#parameter-mapping"
                " to learn the right way to translate this header "
                "manually."
            ),
            b"Zyte-Foo",
            [b"bar"],
            request,
            "Zyte Smart Proxy Manager",
            "Zyte API",
        )
        mock_logger.warning.reset_mock()

        request = Request(
            "https://example.com",
            headers={"X-Crawlera-Foo": "bar"},
            meta={"proxy": "http://apikey:@api.zyte.com:8011"},
        )
        self.assertEqual(mw.process_request(request, self.spider), None)
        mock_logger.warning.assert_called_with(
            (
                "Dropping header %r (%r) from request %r, as this "
                "request is proxied with %s and not with %s, and "
                "automatic translation is not supported for this "
                "header. See "
                "https://docs.zyte.com/zyte-api/migration/zyte/smartproxy.html"
                "#parameter-mapping"
                " to learn the right way to translate this header "
                "manually."
            ),
            b"X-Crawlera-Foo",
            [b"bar"],
            request,
            "Zyte API",
            "Zyte Smart Proxy Manager",
        )
        mock_logger.warning.reset_mock()

        self.spider.zyte_smartproxy_enabled = False
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(self.spider)
        request = Request(
            "https://example.com",
            headers={"Zyte-Foo": "bar", "X-Crawlera-Foo": "bar"},
        )
        self.assertEqual(mw.process_request(request, self.spider), None)
        # No warnings for "drop all" scenarios
        mock_logger.warning.assert_not_called()

    def test_header_based_handling(self):
        self.spider.zyte_smartproxy_enabled = True
        spider = self.spider
        crawler = self._mock_crawler(spider, self.settings)
        mw = self.mwcls.from_crawler(crawler)
        mw.open_spider(spider)
        httpproxy = HttpProxyMiddleware.from_crawler(crawler)

        req = Request("http://example.com")
        assert mw.process_request(req, spider) is None
        assert httpproxy.process_request(req, spider) is None

        count = 0
        res = Response(req.url)
        assert mw.process_response(req, res, spider) is res
        self.assertEqual(crawler.stats.get_value("zyte_smartproxy/response"), None)

        for k, v in RESPONSE_IDENTIFYING_HEADERS:
            count += 1
            res = Response(req.url, headers={k: v})
            assert mw.process_response(req, res, spider) is res
            self.assertEqual(crawler.stats.get_value("zyte_smartproxy/response"), count)

    def test_meta_copy(self):
        """Warn when users copy the proxy key from one response to the next."""
        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        smartproxy = self.mwcls.from_crawler(crawler)
        smartproxy.open_spider(self.spider)
        httpproxy = HttpProxyMiddleware.from_crawler(crawler)
        auth_header = basic_auth_header("apikey", "")

        request1 = Request("https://example.com/a")
        self.assertEqual(smartproxy.process_request(request1, self.spider), None)
        self.assertEqual(httpproxy.process_request(request1, self.spider), None)
        self.assertEqual(request1.meta["proxy"], "http://proxy.zyte.com:8011")
        self.assertEqual(request1.headers[b"Proxy-Authorization"], auth_header)

        request2 = Request("https://example.com/b", meta=dict(request1.meta))
        with patch("scrapy_zyte_smartproxy.middleware.logger") as logger:
            self.assertEqual(smartproxy.process_request(request2, self.spider), None)
        self.assertEqual(httpproxy.process_request(request2, self.spider), None)
        self.assertEqual(request2.meta["proxy"], "http://proxy.zyte.com:8011")
        self.assertEqual(request2.headers[b"Proxy-Authorization"], auth_header)
        expected_calls = [
            call(
                "The value of the 'proxy' meta key of request {request2} "
                "has no API key. You seem to have copied the value of "
                "the 'proxy' request meta key from a response or from a "
                "different request. Copying request meta keys set by "
                "middlewares from one request to another is a bad "
                "practice that can cause issues.".format(request2=request2)
            ),
        ]
        self.assertEqual(logger.warning.call_args_list, expected_calls)

    def test_manual_proxy_same(self):
        """Defining the 'proxy' request meta key with the right URL has the
        same effect as not defining it."""
        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        smartproxy = self.mwcls.from_crawler(crawler)
        smartproxy.open_spider(self.spider)
        httpproxy = HttpProxyMiddleware.from_crawler(crawler)
        auth_header = basic_auth_header("apikey", "")

        meta = {"proxy": "http://apikey:@proxy.zyte.com:8011"}
        request = Request("https://example.com", meta=meta)
        self.assertEqual(smartproxy.process_request(request, self.spider), None)
        self.assertEqual(httpproxy.process_request(request, self.spider), None)
        self.assertEqual(request.meta["proxy"], "http://proxy.zyte.com:8011")
        self.assertEqual(request.headers[b"Proxy-Authorization"], auth_header)

    def test_manual_proxy_without_api_key(self):
        """Defining the 'proxy' request meta key with the right URL but missing
        the API key triggers a warning, and causes the API key to be added."""
        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        smartproxy = self.mwcls.from_crawler(crawler)
        smartproxy.open_spider(self.spider)
        httpproxy = HttpProxyMiddleware.from_crawler(crawler)
        auth_header = basic_auth_header("apikey", "")

        meta = {"proxy": "http://proxy.zyte.com:8011"}
        request = Request("https://example.com", meta=meta)
        with patch("scrapy_zyte_smartproxy.middleware.logger") as logger:
            self.assertEqual(smartproxy.process_request(request, self.spider), None)
        self.assertEqual(httpproxy.process_request(request, self.spider), None)
        self.assertEqual(request.meta["proxy"], "http://proxy.zyte.com:8011")
        self.assertEqual(request.headers[b"Proxy-Authorization"], auth_header)
        expected_calls = [
            call(
                "The value of the 'proxy' meta key of request {request} "
                "has no API key. You seem to have copied the value of "
                "the 'proxy' request meta key from a response or from a "
                "different request. Copying request meta keys set by "
                "middlewares from one request to another is a bad "
                "practice that can cause issues.".format(request=request)
            ),
        ]
        self.assertEqual(logger.warning.call_args_list, expected_calls)

    def test_manual_proxy_different(self):
        """Setting a custom 'proxy' request meta with an unrelated proxy URL
        prevents the middleware from making changes."""
        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        smartproxy = self.mwcls.from_crawler(crawler)
        smartproxy.open_spider(self.spider)
        httpproxy = HttpProxyMiddleware.from_crawler(crawler)

        meta = {"proxy": "http://proxy.example.com:8011"}
        request = Request("https://example.com", meta=meta)
        self.assertEqual(smartproxy.process_request(request, self.spider), None)
        self.assertEqual(httpproxy.process_request(request, self.spider), None)
        self.assertEqual(request.meta["proxy"], "http://proxy.example.com:8011")
        self.assertNotIn(b"Proxy-Authorization", request.headers)

    def test_manual_proxy_different_auth(self):
        """Setting a custom 'proxy' request meta with a matching proxy URL
        but a different key prevents the middleware from making changes."""
        self.spider.zyte_smartproxy_enabled = True
        crawler = self._mock_crawler(self.spider, self.settings)
        smartproxy = self.mwcls.from_crawler(crawler)
        smartproxy.open_spider(self.spider)
        httpproxy = HttpProxyMiddleware.from_crawler(crawler)
        auth_header = basic_auth_header("altkey", "")

        meta = {"proxy": "http://altkey:@proxy.example.com:8011"}
        request = Request("https://example.com", meta=meta)
        self.assertEqual(smartproxy.process_request(request, self.spider), None)
        self.assertEqual(httpproxy.process_request(request, self.spider), None)
        self.assertEqual(request.meta["proxy"], "http://proxy.example.com:8011")
        self.assertEqual(request.headers[b"Proxy-Authorization"], auth_header)
