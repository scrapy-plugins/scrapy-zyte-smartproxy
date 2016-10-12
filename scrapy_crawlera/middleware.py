import os
import logging
import warnings
from collections import defaultdict

from six.moves.urllib.parse import urlparse
from w3lib.http import basic_auth_header
from scrapy import signals
from scrapy.resolver import dnscache
from scrapy.exceptions import ScrapyDeprecationWarning
from twisted.internet.error import ConnectionRefusedError, ConnectionDone


class CrawleraMiddleware(object):

    url = 'http://proxy.crawlera.com:8010'
    maxbans = 400
    ban_code = 503
    download_timeout = 190
    # Handle crawlera server failures
    connection_refused_delay = 90
    preserve_delay = False

    _settings = [
        ('apikey', str),
        ('user', str),
        ('pass', str),
        ('url', str),
        ('maxbans', int),
        ('download_timeout', int),
        ('preserve_delay', bool),
    ]

    def __init__(self, crawler):
        self.crawler = crawler
        self.job_id = os.environ.get('SCRAPY_JOB')
        self._bans = defaultdict(int)
        self._saved_delays = defaultdict(lambda: None)

    @classmethod
    def from_crawler(cls, crawler):
        o = cls(crawler)
        crawler.signals.connect(o.open_spider, signals.spider_opened)
        return o

    def open_spider(self, spider):
        self.enabled = self.is_enabled(spider)
        if not self.enabled:
            return

        for k, type_ in self._settings:
            setattr(self, k, self._get_setting_value(spider, k, type_))

        if '?noconnect' not in self.url:
            self.url += '?noconnect'

        self._proxyauth = self.get_proxyauth(spider)
        logging.info("Using crawlera at %s (user: %s)" % (
            self.url,
            self.apikey[:7] + '...' if self.apikey else self.user))

        if not self.preserve_delay:
            # Setting spider download delay to 0 to get maximum crawl rate
            spider.download_delay = 0
            logging.info(
                "CrawleraMiddleware: disabling download delays on Scrapy side to optimize delays introduced by Crawlera. "
                "To avoid this behaviour you can use the CRAWLERA_PRESERVE_DELAY setting but keep in mind that this may slow down the crawl significantly")

    def _settings_get(self, type_, *a, **kw):
        if type_ is int:
            return self.crawler.settings.getint(*a, **kw)
        elif type_ is bool:
            return self.crawler.settings.getbool(*a, **kw)
        elif type_ is list:
            return self.crawler.settings.getlist(*a, **kw)
        elif type_ is dict:
            return self.crawler.settings.getdict(*a, **kw)
        else:
            return self.crawler.settings.get(*a, **kw)

    def _get_setting_value(self, spider, k, type_):
        if hasattr(spider, 'hubproxy_' + k):
            warnings.warn('hubproxy_%s attribute is deprecated, '
                          'use crawlera_%s instead.' % (k, k),
                          category=ScrapyDeprecationWarning, stacklevel=1)

        if self.crawler.settings.get('HUBPROXY_%s' % k.upper()) is not None:
            warnings.warn('HUBPROXY_%s setting is deprecated, '
                          'use CRAWLERA_%s instead.' % (k.upper(), k.upper()),
                          category=ScrapyDeprecationWarning, stacklevel=1)

        o = getattr(self, k, None)
        s = self._settings_get(
            type_, 'CRAWLERA_' + k.upper(), self._settings_get(
                type_, 'HUBPROXY_' + k.upper(), o))
        return getattr(
            spider, 'crawlera_' + k, getattr(spider, 'hubproxy_' + k, s))

    def is_enabled(self, spider):
        """Hook to enable middleware by custom rules."""
        if hasattr(spider, 'use_hubproxy'):
            warnings.warn('use_hubproxy attribute is deprecated, '
                          'use crawlera_enabled instead.',
                          category=ScrapyDeprecationWarning, stacklevel=1)

        if self.crawler.settings.get('HUBPROXY_ENABLED') is not None:
            warnings.warn('HUBPROXY_ENABLED setting is deprecated, '
                          'use CRAWLERA_ENABLED instead.',
                          category=ScrapyDeprecationWarning, stacklevel=1)
        return (
            getattr(spider, 'crawlera_enabled', False) or
            getattr(spider, 'use_hubproxy', False) or
            self.crawler.settings.getbool("CRAWLERA_ENABLED") or
            self.crawler.settings.getbool("HUBPROXY_ENABLED")
        )

    def get_proxyauth(self, spider):
        """Hook to compute Proxy-Authorization header by custom rules."""
        if self.apikey:
            return basic_auth_header(self.apikey, '')
        return basic_auth_header(self.user, getattr(self, 'pass'))

    def process_request(self, request, spider):
        if self._is_enabled_for_request(request):
            request.meta['proxy'] = self.url
            request.meta['download_timeout'] = self.download_timeout
            request.headers['Proxy-Authorization'] = self._proxyauth
            if self.job_id:
                request.headers['X-Crawlera-Jobid'] = self.job_id
            self.crawler.stats.inc_value('crawlera/request')
            self.crawler.stats.inc_value('crawlera/request/method/%s' % request.method)

    def process_response(self, request, response, spider):
        if not self._is_enabled_for_request(request):
            return response
        key = self._get_slot_key(request)
        self._restore_original_delay(request)
        if response.status == self.ban_code:
            self._bans[key] += 1
            if self._bans[key] > self.maxbans:
                self.crawler.engine.close_spider(spider, 'banned')
            else:
                after = response.headers.get('retry-after')
                if after:
                    self._set_custom_delay(request, float(after))
            self.crawler.stats.inc_value('crawlera/response/banned')
        else:
            self._bans[key] = 0
        # If placed behind `RedirectMiddleware`, it would not count 3xx responses
        self.crawler.stats.inc_value('crawlera/response')
        self.crawler.stats.inc_value('crawlera/response/status/%s' % response.status)
        crawlera_error = response.headers.get('X-Crawlera-Error')
        if crawlera_error:
            self.crawler.stats.inc_value('crawlera/response/error')
            self.crawler.stats.inc_value('crawlera/response/error/%s' % crawlera_error)
        return response

    def process_exception(self, request, exception, spider):
        if not self._is_enabled_for_request(request):
            return
        if isinstance(exception, (ConnectionRefusedError, ConnectionDone)):
            # Handle crawlera downtime
            self._clear_dns_cache()
            self._set_custom_delay(request, self.connection_refused_delay)

    def _clear_dns_cache(self):
        # Scrapy doesn't expire dns records by default, so we force it here,
        # so client can reconnect trough DNS failover.
        dnscache.pop(urlparse(self.url).hostname, None)

    def _is_enabled_for_request(self, request):
        return self.enabled and 'dont_proxy' not in request.meta

    def _get_slot_key(self, request):
        return request.meta.get('download_slot')

    def _get_slot(self, request):
        key = self._get_slot_key(request)
        return key, self.crawler.engine.downloader.slots.get(key)

    def _set_custom_delay(self, request, delay):
        """Set custom delay for slot and save original one."""
        key, slot = self._get_slot(request)
        if not slot:
            return
        if self._saved_delays[key] is None:
            self._saved_delays[key] = slot.delay
        slot.delay = delay

    def _restore_original_delay(self, request):
        """Restore original delay for slot if it was changed."""
        key, slot = self._get_slot(request)
        if not slot:
            return
        if self._saved_delays[key] is not None:
            slot.delay, self._saved_delays[key] = self._saved_delays[key], None
