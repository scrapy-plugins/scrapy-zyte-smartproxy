========
Settings
========

This Scrapy downloader middleware adds some settings to configure how to work
with Zyte Smart Proxy Manager.

ZYTE_SMARTPROXY_APIKEY
----------------------

Default: ``None``

Unique Zyte Smart Proxy Manager API key provided for authentication.

ZYTE_SMARTPROXY_URL
-------------------

Default: ``'http://proxy.zyte.com:8010'``

Zyte Smart Proxy Manager instance URL, it varies depending on adquiring a private or dedicated instance. If Zyte Smart Proxy Manager didn't provide
you with a private instance URL, you don't need to specify it.

ZYTE_SMARTPROXY_MAXBANS
-----------------------

Default: ``400``

Number of consecutive bans from Zyte Smart Proxy Manager necessary to stop the spider.

ZYTE_SMARTPROXY_DOWNLOAD_TIMEOUT
--------------------------------

Default: ``190``

Timeout for processing Zyte Smart Proxy Manager requests. It overrides Scrapy's ``DOWNLOAD_TIMEOUT``.

ZYTE_SMARTPROXY_PRESERVE_DELAY
------------------------------

Default: ``False``

If ``False`` Sets Scrapy's ``DOWNLOAD_DELAY`` to ``0``, making the spider to crawl faster. If set to ``True``, it will
respect the provided ``DOWNLOAD_DELAY`` from Scrapy.

ZYTE_SMARTPROXY_DEFAULT_HEADERS
-------------------------------

Default: ``{}``

Default headers added only to Zyte Smart Proxy Manager requests. Headers defined on ``DEFAULT_REQUEST_HEADERS`` will take precedence as long as the ``ZyteSmartProxyMiddleware`` is placed after the ``DefaultHeadersMiddleware``. Headers set on the requests have precedence over the two settings.

* This is the default behavior, ``DefaultHeadersMiddleware`` default priority is ``400`` and we recommend ``ZyteSmartProxyMiddleware`` priority to be ``610``

ZYTE_SMARTPROXY_BACKOFF_STEP
----------------------------

Default: ``15``

Step size used for calculating exponential backoff according to the formula: ``random.uniform(0, min(max, step * 2 ** attempt))``.

ZYTE_SMARTPROXY_BACKOFF_MAX
---------------------------

Default: ``180``

Max value for exponential backoff as showed in the formula above.

ZYTE_SMARTPROXY_FORCE_ENABLE_ON_HTTP_CODES
------------------------------------------

Default: ``[]``

List of HTTP response status codes that warrant enabling Zyte Smart Proxy Manager for the
corresponding domain.

When a response with one of these HTTP status codes is received after a request
that did not go through Zyte Smart Proxy Manager, the request is retried with Zyte Smart Proxy Manager, and any
new request to the same domain is also sent through Zyte Smart Proxy Manager.
