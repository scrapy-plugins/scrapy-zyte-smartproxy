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


**Hint**: You can also use :ref:`CRAWLERA_USER` and :ref:`CRAWLERA_PASS` instead of :ref:`CRAWLERA_APIKEY`.

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

Remember that you are now making request to Crawlera, and the Crawlera service will be the one actually making the requests to the different sites.

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

This Middleware also adds some configurable Scrapy Settings, check :ref:`the complete list here <settings>`.

All the rest
============

.. toctree::
   :caption: All the rest
   :hidden:

   news

:doc:`news`
    See what has changed in recent Scrapy versions.
