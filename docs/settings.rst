========
Settings
========

This Middleware adds some settings to configure how to work with Crawlera.

CRAWLERA_APIKEY
---------------

Default: ``None``

Unique Crawlera API Key provided for authentication.

CRAWLERA_URL
------------

Default: ``'http://proxy.crawlera.com:8010'``

Crawlera instance url, it varies depending on adquiring a private or dedicated instance. If Crawlera didn't provide
you with a private instance url, you don't need to specify it.

CRAWLERA_MAXBANS
----------------

Default: ``400``

Number of consecutive bans from Crawlera necessary to stop the spider.

CRAWLERA_DOWNLOAD_TIMEOUT
-------------------------

Default: ``190``

Timeout for processing Crawlera requests. It overrides Scrapy's ``DOWNLOAD_TIMEOUT``.

CRAWLERA_PRESERVE_DELAY
-----------------------

Default: ``False``

If ``False`` Sets Scrapy's ``DOWNLOAD_DELAY`` to ``0``, making the spider to crawl faster. If set to ``True``, it will
respect the provided ``DOWNLOAD_DELAY`` from Scrapy.

CRAWLERA_DEFAULT_HEADERS
-----------------------

Default: ``{}``

Default headers added only to crawlera requests. Headers defined on ``DEFAULT_REQUEST_HEADERS`` will take precedence as long as the ``CrawleraMiddleware`` is placed after the ``DefaultHeadersMiddleware``. Headers set on the requests have precedence over the two settings.

* This is the default behavior, ``DefaultHeadersMiddleware`` default priority is ``400`` and we recommend ``CrawleraMiddleware`` priority to be ``610``

CRAWLERA_BACKOFF_STEP
-----------------------

Default: ``15``

Step size used for calculating exponential backoff according to the formula: ``random.uniform(0, min(max, step * 2 ** attempt))``.

CRAWLERA_BACKOFF_MAX
-----------------------

Default: ``180``

Max value for exponential backoff as showed in the formula above.

CRAWLERA_FORCE_ENABLE_ON_HTTP_CODES
------------------------------------

Default: ``[]``

List of http resṕmse status codes that when, ``scrapy-crawlera`` gets a response with one of them and is disabled, it should retry the request forcing the middleware to use crawlera (just for that request).

CRAWLERA_FORCE_ENABLE_FOR_ALL_REQUESTS
---------------------------------------

Default: ``False``

Set this to ``True`` when you want that, after a response with a code set on ``CRAWLERA_FORCE_ENABLE_ON_HTTP_CODES``, ``scrapy-crawlera`` be enabled for all subsequent requests. 
