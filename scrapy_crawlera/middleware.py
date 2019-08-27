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

from scrapy_crawlera.utils import exp_backoff


class CrawleraMiddleware(object):

    url = 'http://proxy.crawlera.com:8010'
    maxbans = 400
    ban_code = 503
    download_timeout = 190
    # Handle crawlera server failures
    connection_refused_delay = 90
    preserve_delay = False
    header_prefix = 'X-Crawlera-'
    conflicting_headers = ('X-Crawlera-Profile', 'X-Crawlera-UA')
    backoff_step = 15
    backoff_max = 180
    exp_backoff = None
    force_enable_on_http_codes = []
    max_auth_retry_times = 10
    enabled_for_domain = {}
    apikey = ""

    _settings = [
        ('apikey', str),
        ('url', str),
        ('maxbans', int),
        ('download_timeout', int),
        ('preserve_delay', bool),
        ('backoff_step', int),
        ('backoff_max', int),
        ('force_enable_on_http_codes', list),
    ]

    def __init__(self, crawler):
        self.crawler = crawler
        self.job_id = os.environ.get('SCRAPY_JOB')
        self.spider = None
        self._bans = defaultdict(int)
        self._saved_delays = defaultdict(lambda: None)

    @classmethod
    def from_crawler(cls, crawler):
        o = cls(crawler)
        crawler.signals.connect(o.open_spider, signals.spider_opened)
        return o

    def open_spider(self, spider):
        self.enabled = self.is_enabled(spider)
        self.spider = spider

        for k, type_ in self._settings:
            setattr(self, k, self._get_setting_value(spider, k, type_))

        self._fix_url_protocol()
        self._headers = self.crawler.settings.get('CRAWLERA_DEFAULT_HEADERS', {}).items()
        self.exp_backoff = exp_backoff(self.backoff_step, self.backoff_max)

        if not self.enabled and not self.force_enable_on_http_codes:
            return

        if not self.apikey:
            logging.warning("Crawlera can't be used without a APIKEY", extra={'spider': spider})
            return

        self._proxyauth = self.get_proxyauth(spider)

        logging.info(
            "Using crawlera at %s (apikey: %s)" % (self.url, self.apikey[:7]),
            extra={'spider': spider},
        )

        if not self.preserve_delay:
            # Setting spider download delay to 0 to get maximum crawl rate
            spider.download_delay = 0
            logging.info(
                "CrawleraMiddleware: disabling download delays on Scrapy side to optimize delays introduced by Crawlera. "
                "To avoid this behaviour you can use the CRAWLERA_PRESERVE_DELAY setting but keep in mind that this may slow down the crawl significantly",
                extra={'spider': spider},
            )

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

    def _fix_url_protocol(self):
        if self.url.startswith('https://'):
            logging.warning('CRAWLERA_URL "%s" set with "https://" protocol.' % self.url)
        elif not self.url.startswith('http://'):
            logging.warning('Adding "http://" to CRAWLERA_URL %s' % self.url)
            self.url = 'http://' + self.url

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
            getattr(spider, 'crawlera_enabled', self.crawler.settings.getbool('CRAWLERA_ENABLED')) or
            getattr(spider, 'use_hubproxy', self.crawler.settings.getbool("HUBPROXY_ENABLED"))
        )

    def get_proxyauth(self, spider):
        """Hook to compute Proxy-Authorization header by custom rules."""
        return basic_auth_header(self.apikey, '')

    def process_request(self, request, spider):
        if self._is_enabled_for_request(request):
            self._set_crawlera_default_headers(request)
            request.meta['proxy'] = self.url
            request.meta['download_timeout'] = self.download_timeout
            request.headers['Proxy-Authorization'] = self._proxyauth
            if self.job_id:
                request.headers['X-Crawlera-Jobid'] = self.job_id
            self.crawler.stats.inc_value('crawlera/request')
            self.crawler.stats.inc_value('crawlera/request/method/%s' % request.method)
        else:
            self._clean_crawlera_headers(request)

    def _is_banned(self, response):
        return (
            response.status == self.ban_code and
            response.headers.get('X-Crawlera-Error') == b'banned'
        )

    def _is_no_available_proxies(self, response):
        return (
            response.status == self.ban_code and
            response.headers.get('X-Crawlera-Error') == b'noslaves'
        )

    def _is_auth_error(self, response):
        return (
            response.status == 407 and
            response.headers.get('X-Crawlera-Error') == b'bad_proxy_auth'
        )

    def process_response(self, request, response, spider):
        if not self._is_enabled_for_request(request):
            return self._handle_not_enabled_response(request, response)

        if not self._is_crawlera_response(response):
            return response

        key = self._get_slot_key(request)
        self._restore_original_delay(request)

        if self._is_no_available_proxies(response) or self._is_auth_error(response):
            if self._is_no_available_proxies(response):
                reason = 'noslaves'
            else:
                reason = 'autherror'
            self._set_custom_delay(request, next(self.exp_backoff), reason=reason)
        else:
            self.crawler.stats.inc_value('crawlera/delay/reset_backoff')
            self.exp_backoff = exp_backoff(self.backoff_step, self.backoff_max)

        if self._is_auth_error(response):
            # When crawlera has issues it might not be able to authenticate users
            # we must retry
            retries = response.meta.get('crawlera_auth_retry_times', 0)
            if retries < self.max_auth_retry_times:
                return self._retry_auth(response, request, spider)
            else:
                self.crawler.stats.inc_value('crawlera/retries/auth/max_reached')
                logging.warning(
                    "Max retries for authentication issues reached, please check auth"
                    " information settings",
                    extra={'spider': self.spider},
                )

        if self._is_banned(response):
            self._bans[key] += 1
            if self._bans[key] > self.maxbans:
                self.crawler.engine.close_spider(spider, 'banned')
            else:
                after = response.headers.get('retry-after')
                if after:
                    self._set_custom_delay(request, float(after), reason='banned')
            self.crawler.stats.inc_value('crawlera/response/banned')
        else:
            self._bans[key] = 0
        # If placed behind `RedirectMiddleware`, it would not count 3xx responses
        self.crawler.stats.inc_value('crawlera/response')
        self.crawler.stats.inc_value('crawlera/response/status/%s' % response.status)
        crawlera_error = response.headers.get('X-Crawlera-Error')
        if crawlera_error:
            self.crawler.stats.inc_value('crawlera/response/error')
            self.crawler.stats.inc_value(
                'crawlera/response/error/%s' % crawlera_error.decode('utf8'))
        return response

    def process_exception(self, request, exception, spider):
        if not self._is_enabled_for_request(request):
            return
        if isinstance(exception, (ConnectionRefusedError, ConnectionDone)):
            # Handle crawlera downtime
            self._clear_dns_cache()
            self._set_custom_delay(request, self.connection_refused_delay, reason='conn_refused')

    def _handle_not_enabled_response(self, request, response):
        if self._should_enable_for_response(response):
            domain = self._get_url_domain(request.url)
            self.enabled_for_domain[domain] = True

            retryreq = request.copy()
            retryreq.dont_filter = True
            self.crawler.stats.inc_value('crawlera/retries/should_have_been_enabled')
            return retryreq
        return response

    def _retry_auth(self, response, request, spider):
        logging.warning(
            "Retrying crawlera request for authentication issue",
            extra={'spider': self.spider},
        )
        retries = response.meta.get('crawlera_auth_retry_times', 0) + 1
        retryreq = request.copy()
        retryreq.meta['crawlera_auth_retry_times'] = retries
        retryreq.dont_filter = True
        self.crawler.stats.inc_value('crawlera/retries/auth')
        return retryreq

    def _clear_dns_cache(self):
        # Scrapy doesn't expire dns records by default, so we force it here,
        # so client can reconnect trough DNS failover.
        dnscache.pop(urlparse(self.url).hostname, None)

    def _should_enable_for_response(self, response):
        return response.status in self.force_enable_on_http_codes

    def _is_enabled_for_request(self, request):
        domain = self._get_url_domain(request.url)
        domain_enabled = self.enabled_for_domain.get(domain, False)
        dont_proxy = request.meta.get('dont_proxy', False)
        return (domain_enabled or self.enabled) and not dont_proxy

    def _get_url_domain(self, url):
        parsed = urlparse(url)
        return parsed.netloc

    def _is_crawlera_response(self, response):
        return bool(response.headers.get("X-Crawlera-Version"))

    def _get_slot_key(self, request):
        return request.meta.get('download_slot')

    def _get_slot(self, request):
        key = self._get_slot_key(request)
        return key, self.crawler.engine.downloader.slots.get(key)

    def _set_custom_delay(self, request, delay, reason=None):
        """Set custom delay for slot and save original one."""
        key, slot = self._get_slot(request)
        if not slot:
            return
        if self._saved_delays[key] is None:
            self._saved_delays[key] = slot.delay
        slot.delay = delay
        if reason is not None:
            self.crawler.stats.inc_value('crawlera/delay/%s' % reason)
            self.crawler.stats.inc_value('crawlera/delay/%s/total' % reason, delay)

    def _restore_original_delay(self, request):
        """Restore original delay for slot if it was changed."""
        key, slot = self._get_slot(request)
        if not slot:
            return
        if self._saved_delays[key] is not None:
            slot.delay, self._saved_delays[key] = self._saved_delays[key], None

    def _clean_crawlera_headers(self, request):
        """Remove X-Crawlera-* headers from the request."""
        targets = [
            header
            for header in request.headers
            if self._is_crawlera_header(header)
        ]
        for header in targets:
            request.headers.pop(header, None)

    def _is_crawlera_header(self, header_name):
        if not header_name:
            return False
        header_name = header_name.decode('utf-8').lower()
        return header_name.startswith(self.header_prefix.lower())

    def _set_crawlera_default_headers(self, request):
        for header, value in self._headers:
            if value is None:
                continue
            request.headers.setdefault(header, value)
        lower_case_headers = [
            header.decode('utf-8').lower() for header in request.headers
        ]
        if all(h.lower() in lower_case_headers for h in self.conflicting_headers):
            # Send a general warning once, and specific urls if LOG_LEVEL = DEBUG
            warnings.warn(
                'The headers %s are conflicting on some of your requests. '
                'Please check https://doc.scrapinghub.com/crawlera.html '
                'for more information. You can set LOG_LEVEL=DEBUG to see the urls with problems'
                % str(self.conflicting_headers)
            )
            logging.debug(
                'The headers %s are conflicting on request %s. X-Crawlera-UA '
                'will be ignored. Please check https://doc.scrapinghub.com/cr'
                'awlera.html for more information'
                % (str(self.conflicting_headers), request.url),
                extra={'spider': self.spider},
            )
