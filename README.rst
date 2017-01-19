===============
scrapy-crawlera
===============

.. image:: https://img.shields.io/pypi/v/scrapy-crawlera.svg
   :target: https://pypi.python.org/pypi/scrapy-crawlera
   :alt: PyPI Version

.. image:: https://travis-ci.org/scrapy-plugins/scrapy-crawlera.svg?branch=master
   :target: http://travis-ci.org/scrapy-plugins/scrapy-crawlera
   :alt: Build Status

.. image:: http://codecov.io/github/scrapy-plugins/scrapy-crawlera/coverage.svg?branch=master
   :target: http://codecov.io/github/scrapy-plugins/scrapy-crawlera?branch=master
   :alt: Code Coverage

scrapy-crawlera provides easy use of `Crawlera <http://scrapinghub.com/crawlera>`_ with Scrapy.

Installation
============

You can install scrapy-crawlera using pip::

    pip install scrapy-crawlera

Configuration
=============

* Add the Crawlera middleware including it into the ``DOWNLOADER_MIDDLEWARES`` in your ``settings.py`` file::

    DOWNLOADER_MIDDLEWARES = {
        ...
        'scrapy_crawlera.CrawleraMiddleware': 610
    }

* Then there are two ways to enable it.

  * Through ``settings.py``::

      CRAWLERA_ENABLED = True
      CRAWLERA_APIKEY = 'apikey'

  * Through spider attributes::

      class MySpider:
          crawlera_enabled = True
          crawlera_apikey = 'apikey'

How to use it
=============

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


Changes
=======

v1.2.2 (2017-01-19)
-------------------

- Fix Crawlera error stats key in Python 3.
- Add support for Python 3.6.


v1.2.1 (2016-10-17)
-------------------

Fix release date in README.


v1.2.0 (2016-10-17)
-------------------

- Recommend middleware order to be ``610`` to run before ``RedirectMiddleware``.
- Change default download timeout to 190s or 3 minutes 10 seconds
  (instead of 1800s or 30 minutes).
- Test and advertize Python 3 compatiblity.
- New ``crawlera/request`` and ``crawlera/request/method/*`` stats counts.
- Clear Scrapy DNS cache for proxy URL in case of connection errors.
- Distribute plugin as universal wheel.
