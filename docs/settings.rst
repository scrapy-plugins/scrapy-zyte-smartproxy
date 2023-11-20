========
Settings
========

This Scrapy downloader middleware adds some settings to configure how to work
with your Zyte proxy service.

ZYTE_SMARTPROXY_APIKEY
----------------------

Default: ``None``

Default API key for your Zyte proxy service.

Note that Zyte API and Zyte Smart Proxy Manager have different API keys.

You can :ref:`override this value on specific requests <override>`.


ZYTE_SMARTPROXY_URL
-------------------

Default: ``'http://proxy.zyte.com:8011'``

Default endpoint for your Zyte proxy service.

For guidelines on setting a value, see the :ref:`initial configuration
instructions <ZYTE_SMARTPROXY_URL>`.

You can :ref:`override this value on specific requests <override>`.

ZYTE_SMARTPROXY_MAXBANS
-----------------------

Default: ``400``

Number of consecutive bans necessary to stop the spider.

ZYTE_SMARTPROXY_DOWNLOAD_TIMEOUT
--------------------------------

Default: ``190``

Timeout for processing proxied requests. It overrides Scrapy's ``DOWNLOAD_TIMEOUT``.

ZYTE_SMARTPROXY_PRESERVE_DELAY
------------------------------

Default: ``False``

If ``False`` sets Scrapy's ``DOWNLOAD_DELAY`` to ``0``, making the spider to crawl faster. If set to ``True``, it will
respect the provided ``DOWNLOAD_DELAY`` from Scrapy.

ZYTE_SMARTPROXY_DEFAULT_HEADERS
-------------------------------

Default: ``{}``

Default headers added only to proxied requests. Headers defined on ``DEFAULT_REQUEST_HEADERS`` will take precedence as long as the ``ZyteSmartProxyMiddleware`` is placed after the ``DefaultHeadersMiddleware``. Headers set on the requests have precedence over the two settings.

* This is the default behavior, ``DefaultHeadersMiddleware`` default priority is ``400`` and we recommend ``ZyteSmartProxyMiddleware`` priority to be ``610``.

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

List of HTTP response status codes that warrant enabling your Zyte proxy
service for the corresponding domain.

When a response with one of these HTTP status codes is received after an
unproxied request, the request is retried with your Zyte proxy service, and any
new request to the same domain is also proxied.
