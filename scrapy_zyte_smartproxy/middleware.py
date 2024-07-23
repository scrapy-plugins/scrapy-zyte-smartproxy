import os
import logging
import warnings
from base64 import urlsafe_b64decode
from collections import defaultdict
try:
    from urllib.request import _parse_proxy
except ImportError:
    from urllib2 import _parse_proxy

from six.moves.urllib.parse import urlparse, urlunparse
from w3lib.http import basic_auth_header
from scrapy import signals
from scrapy.resolver import dnscache
from scrapy.exceptions import ScrapyDeprecationWarning
from twisted.internet.error import ConnectionRefusedError, ConnectionDone

from scrapy_zyte_smartproxy.utils import exp_backoff


logger = logging.getLogger(__name__)


def _remove_auth(auth_proxy_url):
    proxy_type, user, password, hostport = _parse_proxy(auth_proxy_url)
    return urlunparse((proxy_type, hostport, "", "", "", ""))


class ZyteSmartProxyMiddleware(object):

    url = 'http://proxy.zyte.com:8011'
    maxbans = 400
    ban_code = 503
    download_timeout = 190
    # Handle Zyte Smart Proxy Manager server failures
    connection_refused_delay = 90
    preserve_delay = False
    header_prefix = 'X-Crawlera-'  # Deprecated
    header_lowercase_prefixes = ('zyte-', 'x-crawlera-')
    conflicting_headers = ('X-Crawlera-Profile', 'X-Crawlera-UA')
    backoff_step = 15
    backoff_max = 180
    exp_backoff = None
    force_enable_on_http_codes = []
    max_auth_retry_times = 10
    enabled_for_domain = {}
    apikey = ""
    zyte_api_to_spm_translations = {
        b"zyte-device": b"x-crawlera-profile",
        b"zyte-geolocation": b"x-crawlera-region",
        b"zyte-jobid": b"x-crawlera-jobid",
        b"zyte-override-headers": b"x-crawlera-profile-pass",
    }
    spm_to_zyte_api_translations = {v: k for k, v in zyte_api_to_spm_translations.items()}

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
        self._auth_url = None
        # Keys are proxy URLs, values are booleans (True means Zyte API, False
        # means Zyte Smart Proxy Manager).
        self._targets = {}

    @classmethod
    def from_crawler(cls, crawler):
        o = cls(crawler)
        crawler.signals.connect(o.open_spider, signals.spider_opened)
        return o

    def _make_auth_url(self, spider):
        parsed_url = urlparse(self.url)
        auth = self.get_proxyauth(spider)
        if not auth.startswith(b'Basic '):
            raise ValueError(
                'Zyte proxy services only support HTTP basic access '
                'authentication, but %s.%s.get_proxyauth() returned %r'
                % (self.__module__, self.__class__.__name__, auth)
            )
        user_and_colon = urlsafe_b64decode(auth[6:].strip()).decode('utf-8')
        netloc = user_and_colon + '@' + parsed_url.netloc.split('@')[-1]
        parsed_url = parsed_url._replace(netloc=netloc)
        return urlunparse(parsed_url)

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
                "Zyte proxy services cannot be used without an API key",
                extra={'spider': spider},
            )
            return

        self._auth_url = self._make_auth_url(spider)
        self._authless_url = _remove_auth(self._auth_url)

        logger.info(
            "Using Zyte proxy service %s with an API key ending in %s" % (
                self.url, self.apikey[:7]
            ),
            extra={'spider': spider},
        )

        if not self.preserve_delay:
            # Setting spider download delay to 0 to get maximum crawl rate
            spider.download_delay = 0
            logger.info(
                "ZyteSmartProxyMiddleware: disabling download delays in "
                "Scrapy to optimize delays introduced by Zyte proxy services. "
                "To avoid this behaviour you can use the "
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

    def _targets_zyte_api(self, request):
        if self._auth_url is None:
            return False
        auth_url = request.meta.get("proxy", self._auth_url)
        targets_zyte_api = self._targets.get(auth_url, None)
        if targets_zyte_api is None:
            targets_zyte_api = urlparse(auth_url).hostname == "api.zyte.com"
            self._targets[auth_url] = targets_zyte_api
        return targets_zyte_api

    def _translate_headers(self, request, targets_zyte_api):
        translation_dict = (
            self.spm_to_zyte_api_translations if targets_zyte_api
            else self.zyte_api_to_spm_translations
        )
        for header, translation in translation_dict.items():
            if header not in request.headers:
                continue
            request.headers[translation] = value = request.headers.pop(header)
            logger.warning(
                "Translating (and dropping) header %r (%r) as %r on request %r",
                header,
                value,
                translation,
                request,
            )

    def _inc_stat(self, stat, targets_zyte_api, value=1):
        prefix = "zyte_api_proxy" if targets_zyte_api else "zyte_smartproxy"
        self.crawler.stats.inc_value("{}/{}".format(prefix, stat), value)

    def process_request(self, request, spider):
        if self._is_enabled_for_request(request):
            if 'proxy' not in request.meta:
                request.meta['proxy'] = self._auth_url
            elif (
                request.meta['proxy'] == self._authless_url
                and b"Proxy-Authorization" not in request.headers
            ):
                logger.warning(
                    "The value of the 'proxy' meta key of request {request} "
                    "has no API key. You seem to have copied the value of "
                    "the 'proxy' request meta key from a response or from a "
                    "different request. Copying request meta keys set by "
                    "middlewares from one request to another is a bad "
                    "practice that can cause issues.".format(request=request)
                )
                request.meta['proxy'] = self._auth_url
            targets_zyte_api = self._targets_zyte_api(request)
            self._set_zyte_smartproxy_default_headers(request)
            request.meta['download_timeout'] = self.download_timeout
            if self.job_id:
                job_header = 'Zyte-JobId' if targets_zyte_api else 'X-Crawlera-JobId'
                request.headers[job_header] = self.job_id
            user_agent_header = "Zyte-Client" if targets_zyte_api else "X-Crawlera-Client"
            from scrapy_zyte_smartproxy import __version__
            request.headers[user_agent_header] = 'scrapy-zyte-smartproxy/%s' % __version__
            self._inc_stat("request", targets_zyte_api=targets_zyte_api)
            self._inc_stat("request/method/{}".format(request.method), targets_zyte_api=targets_zyte_api)
            self._translate_headers(request, targets_zyte_api=targets_zyte_api)
            self._clean_zyte_smartproxy_headers(request, targets_zyte_api=targets_zyte_api)
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

    def _process_error(self, response):
        if "Zyte-Error" in response.headers:
            value = response.headers.get('Zyte-Error')
            response.headers["X-Crawlera-Error"] = value
            return value
        if "X-Crawlera-Error" in response.headers:
            value = response.headers.get('X-Crawlera-Error')
            response.headers["Zyte-Error"] = value
            return value
        return None

    def process_response(self, request, response, spider):
        zyte_smartproxy_error = self._process_error(response)

        targets_zyte_api = self._targets_zyte_api(request)

        if not self._is_enabled_for_request(request):
            return self._handle_not_enabled_response(request, response, targets_zyte_api=targets_zyte_api)

        if not self._is_zyte_smartproxy_or_zapi_response(response):
            return response

        key = self._get_slot_key(request)
        self._restore_original_delay(request)

        no_proxies = self._is_no_available_proxies(response)
        auth_error = self._is_auth_error(response)
        throttled = (
            response.status == 429 and
            response.headers.get('X-Crawlera-Error') == b'too_many_conns'
        )
        if no_proxies or auth_error or throttled:
            if no_proxies:
                reason = 'noslaves'
            elif auth_error:
                reason = 'autherror'
            else:
                assert throttled
                reason = 'throttled'
            self._set_custom_delay(request, next(self.exp_backoff), reason=reason, targets_zyte_api=targets_zyte_api)
        else:
            self._inc_stat("delay/reset_backoff", targets_zyte_api=targets_zyte_api)
            self.exp_backoff = exp_backoff(self.backoff_step, self.backoff_max)

        if auth_error:
            # When Zyte Smart Proxy Manager has issues it might not be able to
            # authenticate users we must retry
            retries = request.meta.get('zyte_smartproxy_auth_retry_times', 0)
            if retries < self.max_auth_retry_times:
                return self._retry_auth(response, request, spider, targets_zyte_api=targets_zyte_api)
            else:
                self._inc_stat("retries/auth/max_reached", targets_zyte_api=targets_zyte_api)
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
                    self._set_custom_delay(request, float(after), reason='banned', targets_zyte_api=targets_zyte_api)
            self._inc_stat("response/banned", targets_zyte_api=targets_zyte_api)
        else:
            self._bans[key] = 0
        # If placed behind `RedirectMiddleware`, it would not count 3xx responses
        self._inc_stat("response", targets_zyte_api=targets_zyte_api)
        self._inc_stat("response/status/{}".format(response.status), targets_zyte_api=targets_zyte_api)
        if zyte_smartproxy_error:
            self._inc_stat("response/error", targets_zyte_api=targets_zyte_api)
            error_msg = zyte_smartproxy_error.decode('utf8')
            self._inc_stat("response/error/{}".format(error_msg), targets_zyte_api=targets_zyte_api)
        return response

    def process_exception(self, request, exception, spider):
        if not self._is_enabled_for_request(request):
            return
        if isinstance(exception, (ConnectionRefusedError, ConnectionDone)):
            # Handle Zyte Smart Proxy Manager downtime
            self._clear_dns_cache()
            targets_zyte_api = self._targets_zyte_api(request)
            self._set_custom_delay(request, self.connection_refused_delay, reason='conn_refused', targets_zyte_api=targets_zyte_api)

    def _handle_not_enabled_response(self, request, response, targets_zyte_api):
        if self._should_enable_for_response(response):
            domain = self._get_url_domain(request.url)
            self.enabled_for_domain[domain] = True

            retryreq = request.copy()
            retryreq.dont_filter = True
            self._inc_stat("retries/should_have_been_enabled", targets_zyte_api=targets_zyte_api)
            return retryreq
        return response

    def _retry_auth(self, response, request, spider, targets_zyte_api):
        logger.warning(
            (
                "Retrying a request due to an authentication issue with "
                "the configured Zyte proxy service"
            ),
            extra={'spider': self.spider},
        )
        retries = request.meta.get('zyte_smartproxy_auth_retry_times', 0) + 1
        retryreq = request.copy()
        retryreq.meta['zyte_smartproxy_auth_retry_times'] = retries
        retryreq.dont_filter = True
        self._inc_stat("retries/auth", targets_zyte_api=targets_zyte_api)
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

    def _is_zyte_smartproxy_or_zapi_response(self, response):
        return (
            "X-Crawlera-Version" in response.headers
            or "Zyte-Request-Id" in response.headers
            or "zyte-error-type" in response.headers
        )

    def _get_slot_key(self, request):
        return request.meta.get('download_slot')

    def _get_slot(self, request):
        key = self._get_slot_key(request)
        return key, self.crawler.engine.downloader.slots.get(key)

    def _set_custom_delay(self, request, delay, targets_zyte_api, reason=None):
        """Set custom delay for slot and save original one."""
        key, slot = self._get_slot(request)
        if not slot:
            return
        if self._saved_delays[key] is None:
            self._saved_delays[key] = slot.delay
        slot.delay = delay
        if reason is not None:
            self._inc_stat("delay/{}".format(reason), targets_zyte_api=targets_zyte_api)
            self._inc_stat("delay/{}/total".format(reason), value=delay, targets_zyte_api=targets_zyte_api)

    def _restore_original_delay(self, request):
        """Restore original delay for slot if it was changed."""
        key, slot = self._get_slot(request)
        if not slot:
            return
        if self._saved_delays[key] is not None:
            slot.delay, self._saved_delays[key] = self._saved_delays[key], None

    def _clean_zyte_smartproxy_headers(self, request, targets_zyte_api=None):
        """Remove X-Crawlera-* headers from the request."""
        if targets_zyte_api is None:
            prefixes = self.header_lowercase_prefixes
        elif targets_zyte_api:
            prefixes = ('x-crawlera-',)
        else:
            prefixes = ('zyte-',)
        targets = [
            header
            for header in request.headers
            if self._is_zyte_smartproxy_header(header, prefixes)
        ]
        for header in targets:
            value = request.headers.pop(header, None)
            if targets_zyte_api is not None:
                actual_target, header_target = (
                    ("Zyte API", "Zyte Smart Proxy Manager")
                    if targets_zyte_api
                    else ("Zyte Smart Proxy Manager", "Zyte API")
                )
                logger.warning(
                    (
                        "Dropping header %r (%r) from request %r, as this "
                        "request is proxied with %s and not with %s, and "
                        "automatic translation is not supported for this "
                        "header. See "
                        "https://docs.zyte.com/zyte-api/migration/zyte/smartproxy.html#parameter-mapping"
                        " to learn the right way to translate this header "
                        "manually."
                    ),
                    header,
                    value,
                    request,
                    actual_target,
                    header_target,
                )

    def _is_zyte_smartproxy_header(self, header_name, prefixes):
        if not header_name:
            return False
        header_name = header_name.decode('utf-8').lower()
        return any(
            header_name.startswith(prefix)
            for prefix in prefixes
        )

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
