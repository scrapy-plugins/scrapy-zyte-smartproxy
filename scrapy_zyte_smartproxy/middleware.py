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

from scrapy_zyte_smartproxy.utils import exp_backoff


logger = logging.getLogger(__name__)


class ZyteSmartProxyMiddleware(object):

    url = 'http://proxy.zyte.com:8011'
    maxbans = 400
    ban_code = 503
    download_timeout = 190
    # Handle Zyte Smart Proxy Manager server failures
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
        self._headers = self.crawler.settings.get('ZYTE_SMARTPROXY_DEFAULT_HEADERS', {}).items()
        self.exp_backoff = exp_backoff(self.backoff_step, self.backoff_max)

        if not self.enabled and not self.force_enable_on_http_codes:
            return

        if not self.apikey:
            logger.warning(
                "Zyte Smart Proxy Manager cannot be used without an API key",
                extra={'spider': spider},
            )
            return

        self._proxyauth = self.get_proxyauth(spider)

        logger.info(
            "Using Zyte Smart Proxy Manager at %s (apikey: %s)" % (
                self.url, self.apikey[:7]
            ),
            extra={'spider': spider},
        )

        if not self.preserve_delay:
            # Setting spider download delay to 0 to get maximum crawl rate
            spider.download_delay = 0
            logger.info(
                "ZyteSmartProxyMiddleware: disabling download delays in "
                "Scrapy to optimize delays introduced by Zyte Smart Proxy "
                "Manager. To avoid this behaviour you can use the "
                "ZYTE_SMARTPROXY_PRESERVE_DELAY setting, but keep in mind "
                "that this may slow down the crawl significantly",
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
                          'use zyte_smartproxy_%s instead.' % (k, k),
                          category=ScrapyDeprecationWarning, stacklevel=1)

        if self.crawler.settings.get('HUBPROXY_%s' % k.upper()) is not None:
            warnings.warn('HUBPROXY_%s setting is deprecated, '
                          'use ZYTE_SMARTPROXY_%s instead.' % (k.upper(), k.upper()),
                          category=ScrapyDeprecationWarning, stacklevel=1)

        o = getattr(self, k, None)
        s = self._settings_get(
            type_, 'ZYTE_SMARTPROXY_' + k.upper(), self._settings_get(
                type_, 'HUBPROXY_' + k.upper(), o))
        return getattr(
            spider, 'zyte_smartproxy_' + k, getattr(spider, 'hubproxy_' + k, s))

    def _fix_url_protocol(self):
        if self.url.startswith('https://'):
            logger.warning('ZYTE_SMARTPROXY_URL "%s" set with "https://" protocol.' % self.url)
        elif not self.url.startswith('http://'):
            logger.warning('Adding "http://" to ZYTE_SMARTPROXY_URL %s' % self.url)
            self.url = 'http://' + self.url

    def is_enabled(self, spider):
        """Hook to enable middleware by custom rules."""
        if hasattr(spider, 'use_hubproxy'):
            warnings.warn('use_hubproxy attribute is deprecated, '
                          'use zyte_smartproxy_enabled instead.',
                          category=ScrapyDeprecationWarning, stacklevel=1)

        if self.crawler.settings.get('HUBPROXY_ENABLED') is not None:
            warnings.warn('HUBPROXY_ENABLED setting is deprecated, '
                          'use ZYTE_SMARTPROXY_ENABLED instead.',
                          category=ScrapyDeprecationWarning, stacklevel=1)
        return (
            getattr(spider, 'zyte_smartproxy_enabled', self.crawler.settings.getbool('ZYTE_SMARTPROXY_ENABLED')) or
            getattr(spider, 'use_hubproxy', self.crawler.settings.getbool("HUBPROXY_ENABLED"))
        )

    def get_proxyauth(self, spider):
        """Hook to compute Proxy-Authorization header by custom rules."""
        return basic_auth_header(self.apikey, '')

    def process_request(self, request, spider):
        from scrapy_zyte_smartproxy import __version__
        if self._is_enabled_for_request(request):
            self._set_zyte_smartproxy_default_headers(request)
            request.meta['proxy'] = self.url
            request.meta['download_timeout'] = self.download_timeout
            request.headers['Proxy-Authorization'] = self._proxyauth
            if self.job_id:
                request.headers['X-Crawlera-Jobid'] = self.job_id
            request.headers['X-Crawlera-Client'] = 'scrapy-zyte-smartproxy/%s' % __version__
            self.crawler.stats.inc_value('zyte_smartproxy/request')
            self.crawler.stats.inc_value('zyte_smartproxy/request/method/%s' % request.method)
        else:
            self._clean_zyte_smartproxy_headers(request)

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

        if not self._is_zyte_smartproxy_response(response):
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
            self.crawler.stats.inc_value('zyte_smartproxy/delay/reset_backoff')
            self.exp_backoff = exp_backoff(self.backoff_step, self.backoff_max)

        if self._is_auth_error(response):
            # When Zyte Smart Proxy Manager has issues it might not be able to
            # authenticate users we must retry
            retries = request.meta.get('zyte_smartproxy_auth_retry_times', 0)
            if retries < self.max_auth_retry_times:
                return self._retry_auth(response, request, spider)
            else:
                self.crawler.stats.inc_value('zyte_smartproxy/retries/auth/max_reached')
                logger.warning(
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
            self.crawler.stats.inc_value('zyte_smartproxy/response/banned')
        else:
            self._bans[key] = 0
        # If placed behind `RedirectMiddleware`, it would not count 3xx responses
        self.crawler.stats.inc_value('zyte_smartproxy/response')
        self.crawler.stats.inc_value('zyte_smartproxy/response/status/%s' % response.status)
        zyte_smartproxy_error = response.headers.get('X-Crawlera-Error')
        if zyte_smartproxy_error:
            self.crawler.stats.inc_value('zyte_smartproxy/response/error')
            self.crawler.stats.inc_value(
                'zyte_smartproxy/response/error/%s' % zyte_smartproxy_error.decode('utf8'))
        return response

    def process_exception(self, request, exception, spider):
        if not self._is_enabled_for_request(request):
            return
        if isinstance(exception, (ConnectionRefusedError, ConnectionDone)):
            # Handle Zyte Smart Proxy Manager downtime
            self._clear_dns_cache()
            self._set_custom_delay(request, self.connection_refused_delay, reason='conn_refused')

    def _handle_not_enabled_response(self, request, response):
        if self._should_enable_for_response(response):
            domain = self._get_url_domain(request.url)
            self.enabled_for_domain[domain] = True

            retryreq = request.copy()
            retryreq.dont_filter = True
            self.crawler.stats.inc_value('zyte_smartproxy/retries/should_have_been_enabled')
            return retryreq
        return response

    def _retry_auth(self, response, request, spider):
        logger.warning(
            "Retrying a Zyte Smart Proxy Manager request due to an "
            "authentication issue",
            extra={'spider': self.spider},
        )
        retries = request.meta.get('zyte_smartproxy_auth_retry_times', 0) + 1
        retryreq = request.copy()
        retryreq.meta['zyte_smartproxy_auth_retry_times'] = retries
        retryreq.dont_filter = True
        self.crawler.stats.inc_value('zyte_smartproxy/retries/auth')
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

    def _is_zyte_smartproxy_response(self, response):
        return bool("X-Crawlera-Version" in response.headers)

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
            self.crawler.stats.inc_value('zyte_smartproxy/delay/%s' % reason)
            self.crawler.stats.inc_value('zyte_smartproxy/delay/%s/total' % reason, delay)

    def _restore_original_delay(self, request):
        """Restore original delay for slot if it was changed."""
        key, slot = self._get_slot(request)
        if not slot:
            return
        if self._saved_delays[key] is not None:
            slot.delay, self._saved_delays[key] = self._saved_delays[key], None

    def _clean_zyte_smartproxy_headers(self, request):
        """Remove X-Crawlera-* headers from the request."""
        targets = [
            header
            for header in request.headers
            if self._is_zyte_smartproxy_header(header)
        ]
        for header in targets:
            request.headers.pop(header, None)

    def _is_zyte_smartproxy_header(self, header_name):
        if not header_name:
            return False
        header_name = header_name.decode('utf-8').lower()
        return header_name.startswith(self.header_prefix.lower())

    def _set_zyte_smartproxy_default_headers(self, request):
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
                'Please check '
                'https://docs.zyte.com/smart-proxy-manager.html#request-headers '
                'for more information. You can set LOG_LEVEL=DEBUG to see the '
                'urls with problems.'
                % str(self.conflicting_headers)
            )
            logger.debug(
                'The headers %s are conflicting on request %s. X-Crawlera-UA '
                'will be ignored. Please check '
                'https://docs.zyte.com/smart-proxy-manager.html#request-headers '
                'for more information'
                % (str(self.conflicting_headers), request.url),
                extra={'spider': self.spider},
            )
