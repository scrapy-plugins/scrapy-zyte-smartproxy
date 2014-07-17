from collections import defaultdict
import warnings

from w3lib.http import basic_auth_header
from scrapy import log, signals
from scrapy.exceptions import ScrapyDeprecationWarning
from twisted.internet.error import ConnectionRefusedError


class CrawleraMiddleware(object):

    url = 'http://proxy.crawlera.com:8010'
    maxbans = 20
    ban_code = 503
    download_timeout = 1800
    # Handle crawlera server failures
    connection_refused_delay = 90
    preserve_delay = False

    _settings = [
        'user',
        'pass',
        'url',
        'maxbans',
        'download_timeout',
        'preserve_delay',
    ]

    def __init__(self, crawler):
        self.crawler = crawler
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

        for k in self._settings:
            setattr(self, k, self._get_setting_value(spider, k))
        if '?noconnect' not in self.url:
            self.url += '?noconnect'

        self._proxyauth = self.get_proxyauth(spider)
        log.msg("Using crawlera at %s (user: %s)" % (self.url, self.user),
                spider=spider)

        if not self.preserve_delay:
            # Setting spider download delay to 0 to get maximum crawl rate
            spider.download_delay = 0
            log.msg("Setting spider download delay to 0. It's default "
                    "CrawleraMiddleware behavior, to preserve original delay"
                    " set CRAWLERA_PRESERVE_DELAY = True in settings.",
                    spider=spider)

    def _get_setting_value(self, spider, k):
        if hasattr(spider, 'hubproxy_' + k):
            warnings.warn('hubproxy_%s attribute is deprecated, '
                          'use crawlera_%s instead.' % (k, k),
                          category=ScrapyDeprecationWarning, stacklevel=1)

        if self.crawler.settings.get('HUBPROXY_%s' % k.upper()) is not None:
            warnings.warn('HUBPROXY_%s setting is deprecated, '
                          'use CRAWLERA_%s instead.' % (k.upper(), k.upper()),
                          category=ScrapyDeprecationWarning, stacklevel=1)

        o = getattr(self, k, None)
        s = self.crawler.settings.get('CRAWLERA_' + k.upper(),
            self.crawler.settings.get('HUBPROXY_' + k.upper(), o))
        return getattr(spider, 'crawlera_' + k,
               getattr(spider, 'hubproxy_' + k, s))

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
        return basic_auth_header(self.user, getattr(self, 'pass'))

    def process_request(self, request, spider):
        if self._is_enabled_for_request(request):
            request.meta['proxy'] = self.url
            request.meta['download_timeout'] = self.download_timeout
            request.headers['Proxy-Authorization'] = self._proxyauth

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
        else:
            self._bans[key] = 0
        return response

    def process_exception(self, request, exception, spider):
        if not self._is_enabled_for_request(request):
            return
        if isinstance(exception, ConnectionRefusedError):
            # Handle crawlera downtime
            self._set_custom_delay(request, self.connection_refused_delay)

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
