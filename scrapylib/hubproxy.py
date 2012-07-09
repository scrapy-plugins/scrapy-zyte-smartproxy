from w3lib.http import basic_auth_header
from scrapy.exceptions import NotConfigured
from scrapy.xlib.pydispatch import dispatcher
from scrapy import log, signals

class HubProxyMiddleware(object):

    url = 'http://proxy.scrapinghub.com:8010'
    maxbans = 20
    ban_code = 503

    @classmethod
    def from_crawler(cls, crawler):
        o = cls()
        o.crawler = crawler
        dispatcher.connect(o.open_spider, signals.spider_opened)
        return o

    def open_spider(self, spider):
        self.enabled = getattr(spider, 'use_hubproxy', False) \
                or 'hubproxy' in self.crawler.settings.getlist('SHUB_JOB_TAGS')
        if not self.enabled:
            return

        self.user = getattr(spider, 'hubproxy_user', self.crawler.settings['HUBPROXY_USER'])
        self.password = getattr(spider, 'hubproxy_pass', self.crawler.settings['HUBPROXY_PASS'])
        self.url = self.crawler.settings.get('HUBPROXY_URL', self.url)
        self.maxbans = self.crawler.settings.get('HUBPROXY_MAXBANS', self.maxbans)
        self.bans = 0
        self.auth = basic_auth_header(self.user, self.password)
        log.msg("Using hubproxy at %s (user: %s)" % (self.url, self.user), spider=spider)

    def process_request(self, request, spider):
        if self.enabled:
            request.meta['proxy'] = self.url
            request.headers['Proxy-Authorization'] = self.auth

    def process_response(self, request, response, spider):
        if response.status == self.ban_code:
            self.bans += 1
            if self.bans > self.maxbans:
                self.crawler.engine.close_spider(spider, 'banned')
        else:
            self.bans = 0
        return response
