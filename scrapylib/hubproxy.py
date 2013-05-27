from .crawlera import CrawleraMiddleware


class HubProxyMiddleware(CrawleraMiddleware):

    def __init__(self, *args, **kwargs):
        import warnings
        from scrapy.exceptions import ScrapyDeprecationWarning
        warnings.warn('scrapylib.hubproxy.HubProxyMiddleware is deprecated, '
                      'use scrapy.crawlera.CrawleraMiddleware instead. Also '
                      'rename use_hubproxy attribute by crawlera_enabled, '
                      'and HUBPROXY_ENABLED setting by CRAWLERA_ENABLED',
                      category=ScrapyDeprecationWarning, stacklevel=1)
        super(HubProxyMiddleware, self).__init__(*args, **kwargs)

    def is_enabled(self, spider):
        """Hook to enable middleware by custom rules"""
        return getattr(spider, 'use_hubproxy', False) \
            or self.crawler.settings.getbool("HUBPROXY_ENABLED")

    def _get_setting_value(self, spider, k):
        o = getattr(self, k, None)
        s = self.crawler.settings.get('HUBPROXY_' + k.upper(), o)
        return getattr(spider, 'hubproxy_' + k, s)
