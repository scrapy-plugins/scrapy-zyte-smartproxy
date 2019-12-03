=======================================
scrapy-crawlera |version| documentation
=======================================

scrapy-crawlera is a Scrapy `Downloader Middleware <https://doc.scrapy.org/en/latest/topics/downloader-middleware.html#downloader-middleware>`_
to interact with `Crawlera <http://scrapinghub.com/crawlera>`_ automatically.

Configuration
=============

.. toctree::
   :caption: Configuration


* Add the Crawlera middleware including it into the ``DOWNLOADER_MIDDLEWARES`` in your ``settings.py`` file::

    DOWNLOADER_MIDDLEWARES = {
        ...
        'scrapy_crawlera.CrawleraMiddleware': 610
    }

* Then there are two ways to enable it

  * Through ``settings.py``::

      CRAWLERA_ENABLED = True
      CRAWLERA_APIKEY = 'apikey'

  * Through spider attributes::

      class MySpider:
          crawlera_enabled = True
          crawlera_apikey = 'apikey'


* (optional) If you are not using the default Crawlera proxy (``http://proxy.crawlera.com:8010``),
  for example if you have a dedicated or private instance,
  make sure to also set ``CRAWLERA_URL`` in ``settings.py``, e.g.::

    CRAWLERA_URL = 'http://myinstance.crawlera.com:8010'

How to use it
=============

.. toctree::
   :caption: How to use it
   :hidden:

   settings

:doc:`settings`
    All configurable Scrapy Settings added by the Middleware.


With the middleware, the usage of crawlera is automatic, every request will go through crawlera without nothing to worry about.
If you want to *disable* crawlera on a specific Request, you can do so by updating `meta` with `dont_proxy=True`::


    scrapy.Request(
        'http://example.com',
        meta={
            'dont_proxy': True,
            ...
        },
    )


Remember that you are now making requests to Crawlera, and the Crawlera service will be the one actually making the requests to the different sites.

If you need to specify special `Crawlera Headers <https://doc.scrapinghub.com/crawlera.html#request-headers>`_, just apply them as normal `Scrapy Headers <https://doc.scrapy.org/en/latest/topics/request-response.html#scrapy.http.Request.headers>`_.

Here we have an example of specifying a Crawlera header into a Scrapy request::

    scrapy.Request(
        'http://example.com',
        headers={
            'X-Crawlera-Max-Retries': 1,
            ...
        },
    )

Remember that you could also set which headers to use by default by all
requests with `DEFAULT_REQUEST_HEADERS <http://doc.scrapy.org/en/1.0/topics/settings.html#default-request-headers>`_

.. note:: Crawlera headers are removed from requests when the middleware is activated but Crawlera
    is disabled. For example, if you accidentally disable Crawlera via ``crawlera_enabled = False``
    but keep sending ``X-Crawlera-*`` headers in your requests, those will be removed from the
    request headers.

This Middleware also adds some configurable Scrapy Settings, check :ref:`the complete list here <settings>`.


Reusing sessions
================

To create a request in a callback and have that request reuse the same Crawlera
session as the callback response, you have to write something like::

    def callback(self, response):
        session = response.headers.get('X-Crawlera-Session')
        # …
        headers = {}
        if session:
            headers = {'X-Crawlera-Session': session}
        yield Request(url, callback=self.callback, headers=headers)

scrapy-crawlera provides an optional spider middleware that, if enabled, allows
setting  ``crawlera_session_reuse`` to ``True`` in your request to reuse the
Crawlera session from the source response::

    def callback(self, response):
        meta = {'crawlera_session_reuse': True}
        yield Request(url, callback=self.callback, meta=meta)

To enable the Crawlera session reuse spider middleware, add it to your
``SPIDER_MIDDLEWARES`` setting::

    SPIDER_MIDDLEWARES = {
        'scrapy_crawlera.CrawleraSessionReuseMiddleware': 1000,
    }

By default, ``CrawleraSessionReuseMiddleware`` removes ``X-Crawlera-Session``
from the request headers if the source response did not use a Crawlera session,
or the source Crawlera session ID was bad. Use the
``CRAWLERA_SESSION_REUSE_DEFAULT_SESSION`` setting to set a fallback Crawlera
session value instead. For example, to create a new Crawlera session on
requests that come from responses without a Crawlera session or with a bad
Crawlera session ID::

    CRAWLERA_SESSION_REUSE_DEFAULT_SESSION = 'create'


All the rest
============

.. toctree::
   :caption: All the rest
   :hidden:

   news

:doc:`news`
    See what has changed in recent scrapy-crawlera versions.
