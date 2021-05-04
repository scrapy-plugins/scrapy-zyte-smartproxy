==============================================
scrapy-zyte-smartproxy |version| documentation
==============================================

scrapy-zyte-smartproxy is a `Scrapy downloader middleware`_ to interact with
`Zyte Smart Proxy Manager`_ (formerly Crawlera) automatically.

.. _Scrapy downloader middleware: https://doc.scrapy.org/en/latest/topics/downloader-middleware.html
.. _Zyte Smart Proxy Manager: https://www.zyte.com/smart-proxy-manager/

Configuration
=============

.. toctree::
   :caption: Configuration


* Add the Zyte Smart Proxy Manager middleware including it into the ``DOWNLOADER_MIDDLEWARES`` in your ``settings.py`` file::

    DOWNLOADER_MIDDLEWARES = {
        ...
        'scrapy_zyte_smartproxy.ZyteSmartProxyMiddleware': 610
    }

* Then there are two ways to enable it

  * Through ``settings.py``::

      ZYTE_SMARTPROXY_ENABLED = True
      ZYTE_SMARTPROXY_APIKEY = 'apikey'

  * Through spider attributes::

      class MySpider:
          zyte_smartproxy_enabled = True
          zyte_smartproxy_apikey = 'apikey'


* (optional) If you are not using the default Zyte Smart Proxy Manager proxy (``http://proxy.zyte.com:8011``),
  for example if you have a dedicated or private instance,
  make sure to also set ``ZYTE_SMARTPROXY_URL`` in ``settings.py``, e.g.::

    ZYTE_SMARTPROXY_URL = 'http://myinstance.zyte.com:8011'

How to use it
=============

.. toctree::
   :caption: How to use it
   :hidden:

   settings

:doc:`settings`
    All configurable Scrapy Settings added by the Middleware.


With the middleware, the usage of Zyte Smart Proxy Manager is automatic, every request will go through Zyte Smart Proxy Manager without nothing to worry about.
If you want to *disable* Zyte Smart Proxy Manager on a specific Request, you can do so by updating `meta` with `dont_proxy=True`::


    scrapy.Request(
        'http://example.com',
        meta={
            'dont_proxy': True,
            ...
        },
    )


Remember that you are now making requests to Zyte Smart Proxy Manager, and the Zyte Smart Proxy Manager service will be the one actually making the requests to the different sites.

If you need to specify special `Zyte Smart Proxy Manager headers <https://docs.zyte.com/smart-proxy-manager.html#request-headers>`_, just apply them as normal `Scrapy headers <https://doc.scrapy.org/en/latest/topics/request-response.html#scrapy.http.Request.headers>`_.

Here we have an example of specifying a Zyte Smart Proxy Manager header into a Scrapy request::

    scrapy.Request(
        'http://example.com',
        headers={
            'X-Crawlera-Max-Retries': 1,
            ...
        },
    )

Remember that you could also set which headers to use by default by all
requests with `DEFAULT_REQUEST_HEADERS <http://doc.scrapy.org/en/1.0/topics/settings.html#default-request-headers>`_

.. note:: Zyte Smart Proxy Manager headers are removed from requests when the middleware is activated but Zyte Smart Proxy Manager
    is disabled. For example, if you accidentally disable Zyte Smart Proxy Manager via ``zyte_smartproxy_enabled = False``
    but keep sending ``X-Crawlera-*`` headers in your requests, those will be removed from the
    request headers.

This Middleware also adds some configurable Scrapy Settings, check :ref:`the complete list here <settings>`.

All the rest
============

.. toctree::
   :caption: All the rest
   :hidden:

   news

:doc:`news`
    See what has changed in recent scrapy-zyte-smartproxy versions.
