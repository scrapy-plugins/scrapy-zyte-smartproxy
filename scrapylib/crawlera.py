import warnings
from scrapy.exceptions import ScrapyDeprecationWarning
from collections import defaultdict
from w3lib.http import basic_auth_header
from scrapy import log, signals


class CrawleraMiddleware(object):

    url = 'http://proxy.crawlera.com:8010'
    maxbans = 20
    ban_code = 503
    download_timeout = 1800

    @classmethod
    def from_crawler(cls, crawler):
        o = cls()
        o.crawler = crawler
        o._bans = defaultdict(int)
        crawler.signals.connect(o.open_spider, signals.spider_opened)
        return o

    def open_spider(self, spider):
        self.enabled = self.is_enabled(spider)
        if not self.enabled:
            return

        for k in ('user', 'pass', 'url', 'maxbans', 'download_timeout'):
            v = self._get_setting_value(spider, k)
            if k == 'url' and '?noconnect' not in v:
                v += '?noconnect'
            setattr(self, k, v)

        self._proxyauth = self.get_proxyauth(spider)
        log.msg("Using crawlera at %s (user: %s)" % (self.url, self.user), spider=spider)

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
        """Hook to enable middleware by custom rules"""
        if hasattr(spider, 'use_hubproxy'):
            warnings.warn('use_hubproxy attribute is deprecated, '
                          'use crawlera_enabled instead.',
                          category=ScrapyDeprecationWarning, stacklevel=1)

        if self.crawler.settings.get('HUBPROXY_ENABLED') is not None:
            warnings.warn('HUBPROXY_ENABLED setting is deprecated, '
                          'use CRAWLERA_ENABLED instead.',
                          category=ScrapyDeprecationWarning, stacklevel=1)

        return getattr(spider, 'crawlera_enabled', False) \
            or getattr(spider, 'use_hubproxy', False) \
            or self.crawler.settings.getbool("CRAWLERA_ENABLED") \
            or self.crawler.settings.getbool("HUBPROXY_ENABLED")

    def get_proxyauth(self, spider):
        """Hook to compute Proxy-Authorization header by custom rules"""
        return basic_auth_header(self.user, getattr(self, 'pass'))

    def process_request(self, request, spider):
        if self.enabled and 'dont_proxy' not in request.meta:
            request.meta['proxy'] = self.url
            request.meta['download_timeout'] = self.download_timeout
            request.headers['Proxy-Authorization'] = self._proxyauth

    def process_response(self, request, response, spider):
        if not self.enabled:
            return response

        if response.status == self.ban_code:
            key = request.meta.get('download_slot')
            self._bans[key] += 1
            if self._bans[key] > self.maxbans:
                self.crawler.engine.close_spider(spider, 'banned')
            else:
                after = response.headers.get('retry-after')
                if after:
                    key, slot = self._get_slot(request, spider)
                    if slot:
                        slot.delay = float(after)
        else:
            key, slot = self._get_slot(request, spider)
            if slot:
                slot.delay = 0
            self._bans[key] = 0

        return response

    def _get_slot(self, request, spider):
        key = request.meta.get('download_slot')
        return key, self.crawler.engine.downloader.slots.get(key)
