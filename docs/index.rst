==============================================
scrapy-zyte-smartproxy |version| documentation
==============================================

.. toctree::
   :hidden:

   headers
   settings
   news

scrapy-zyte-smartproxy is a `Scrapy downloader middleware`_ to use one of
Zyte’s proxy APIs: either the proxy API of `Zyte API`_ or `Zyte Smart Proxy
Manager`_ (formerly Crawlera).

.. _Scrapy downloader middleware: https://doc.scrapy.org/en/latest/topics/downloader-middleware.html
.. _Zyte API: https://docs.zyte.com/zyte-api/get-started.html
.. _Zyte Smart Proxy Manager: https://www.zyte.com/smart-proxy-manager/

Configuration
=============

#.  Add the downloader middleware to your ``DOWNLOADER_MIDDLEWARES`` Scrapy
    setting:

    .. code-block:: python
        :caption: settings.py

        DOWNLOADER_MIDDLEWARES = {
            ...
            'scrapy_zyte_smartproxy.ZyteSmartProxyMiddleware': 610
        }

#.  Enable the middleware and configure your API key, either through Scrapy
    settings:

    .. code-block:: python
        :caption: settings.py

        ZYTE_SMARTPROXY_ENABLED = True
        ZYTE_SMARTPROXY_APIKEY = 'apikey'

    Or through spider attributes:

    .. code-block:: python

        class MySpider(scrapy.Spider):
            zyte_smartproxy_enabled = True
            zyte_smartproxy_apikey = 'apikey'

.. _ZYTE_SMARTPROXY_URL:

#.  Set the ``ZYTE_SMARTPROXY_URL`` Scrapy setting as needed:

    -   To use the proxy API of Zyte API, set it to
        ``http://api.zyte.com:8011``:

        .. code-block:: python
            :caption: settings.py

                ZYTE_SMARTPROXY_URL = "http://api.zyte.com:8011"

    -   To use the default Zyte Smart Proxy Manager endpoint, leave it unset.

    -   To use a custom Zyte Smart Proxy Manager endpoint, in case you have a
        dedicated or private instance, set it to your custom endpoint. For
        example:

        .. code-block:: python
            :caption: settings.py

                ZYTE_SMARTPROXY_URL = "http://myinstance.zyte.com:8011"


Usage
=====

Once the downloader middleware is properly configured, every request goes
through the configured Zyte proxy API.

.. _override:

Although the plugin configuration only allows defining a single proxy API
endpoint and API key, it is possible to override them for specific requests, so
that you can use different combinations for different requests within the same
spider.

To **override** which combination of endpoint and API key is used for a given
request, set ``proxy`` in the request metadata to a URL indicating both the
target endpoint and the API key to use. For example:

    .. code-block:: python

        scrapy.Request(
            "https://topscrape.com",
            meta={
                "proxy": "http://YOUR_API_KEY@api.zyte.com:8011",
                ...
            },
        )

.. TODO: Check that a colon after the API key is not needed in this case.

To **disable** proxying altogether for a given request, set ``dont_proxy`` to
``True`` on the request metadata:

    .. code-block:: python

        scrapy.Request(
            "https://topscrape.com",
            meta={
                "dont_proxy": True,
                ...
            },
        )

You can set `Zyte API proxy headers`_ or `Zyte Smart Proxy Manager headers`_ as
regular `Scrapy headers`_, e.g. using the ``headers`` parameter of ``Request``
or using the DEFAULT_REQUEST_HEADERS_ setting. For example:

    .. code-block:: python

        scrapy.Request(
            "https://topscrape.com",
            headers={
                "Zyte-Geolocation": "FR",
                ...
            },
        )

.. _Zyte API proxy headers: https://docs.zyte.com/zyte-api/usage/proxy-api.html
.. _Zyte Smart Proxy Manager headers: https://docs.zyte.com/smart-proxy-manager.html#request-headers
.. _Scrapy headers: https://doc.scrapy.org/en/latest/topics/request-response.html#scrapy.http.Request.headers
.. _DEFAULT_REQUEST_HEADERS: https://doc.scrapy.org/en/latest/topics/settings.html#default-request-headers

For information about proxy-specific header processing, see :doc:`headers`.

See also :ref:`settings` for the complete list of settings that this downloader
middleware supports.
