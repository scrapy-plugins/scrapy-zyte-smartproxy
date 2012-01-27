from w3lib.http import basic_auth_header
from scrapy.exceptions import NotConfigured
from scrapy.xlib.pydispatch import dispatcher
from scrapy import log, signals

class HubProxyMiddleware(object):

    default_url = 'http://proxy.scrapinghub.com:8010'
    ban_code = 503

    def __init__(self, user, password, maxbans, url, crawler, enabled=False):
        self.url = url
        self.user = user
        self.auth = basic_auth_header(user, password)
        self.crawler = crawler
        self.enabled = enabled
        self.maxbans = maxbans
        self.bans = 0

    @classmethod
    def from_crawler(cls, crawler):
        user = crawler.settings['HUBPROXY_USER']
        password = crawler.settings['HUBPROXY_PASS']
        url = crawler.settings.get('HUBPROXY_URL', cls.default_url)
        maxbans = crawler.settings.get('HUBPROXY_MAXBANS', 20)
        enabled = 'hubproxy' in crawler.settings.getlist('SHUB_JOB_TAGS')
        if not user:
            raise NotConfigured

        o = cls(user, password, maxbans, url, crawler, enabled)
        dispatcher.connect(o.open_spider, signals.spider_opened)
        return o

    def open_spider(self, spider):
        try:
            self.enabled = spider.use_hubproxy
        except AttributeError:
            pass

        if self.enabled:
            log.msg("Using hubproxy at %s (user: %s)" % (self.url, self.user),
                spider=spider)

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
