from .crawlera import CrawleraMiddleware


class HubProxyMiddleware(CrawleraMiddleware):

    def __init__(self, *args, **kwargs):
        import warnings
        from scrapy.exceptions import ScrapyDeprecationWarning
        warnings.warn('scrapylib.hubproxy.HubProxyMiddleware is deprecated, '
                      'use scrapylib.crawlera.CrawleraMiddleware instead.',
                      category=ScrapyDeprecationWarning, stacklevel=1)
        super(HubProxyMiddleware, self).__init__(*args, **kwargs)
