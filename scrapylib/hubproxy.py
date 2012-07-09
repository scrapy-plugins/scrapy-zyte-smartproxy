from w3lib.http import basic_auth_header
from scrapy.xlib.pydispatch import dispatcher
from scrapy import log, signals


class HubProxyMiddleware(object):

    url = 'http://proxy.scrapinghub.com:8010'
    maxbans = 20
    ban_code = 503
    download_timeout = 1800

    @classmethod
    def from_crawler(cls, crawler):
        o = cls()
        o.crawler = crawler
        dispatcher.connect(o.open_spider, signals.spider_opened)
        return o

    def open_spider(self, spider):
        self.enabled = self.is_enabled(spider)
        if not self.enabled:
            return

        for k in ('user', 'pass', 'url', 'maxbans', 'download_timeout'):
            o = getattr(self, k, None)
            s = self.crawler.settings.get('HUBPROXY_' + k.upper(), o)
            v = getattr(spider, 'hubproxy_' + k, s)
            setattr(self, k, v)

        self._bans = 0
        self._proxyauth = self.get_proxyauth(spider)
        log.msg("Using hubproxy at %s (user: %s)" % (self.url, self.user), spider=spider)

    def is_enabled(self, spider):
        """Hook to enable middleware by custom rules"""
        return getattr(spider, 'use_hubproxy', False) \
                or 'hubproxy' in self.crawler.settings.getlist('SHUB_JOB_TAGS')

    def get_proxyauth(self, spider):
        """Hook to compute Proxy-Authorization header by custom rules"""
        return basic_auth_header(self.user, getattr(self, 'pass'))

    def process_request(self, request, spider):
        if self.enabled:
            request.meta['proxy'] = self.url
            request.meta['download_timeout'] = self.download_timeout
            request.headers['Proxy-Authorization'] = self._proxyauth

    def process_response(self, request, response, spider):
        if response.status == self.ban_code:
            self._bans += 1
            if self._bans > self.maxbans:
                self.crawler.engine.close_spider(spider, 'banned')
        else:
            self._bans = 0
        return response
