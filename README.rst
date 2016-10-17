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

You can then enable the middleware in your `settings.py`::

    DOWNLOADER_MIDDLEWARES = {
        ...
        'scrapy_crawlera.CrawleraMiddleware': 610
    }


Credentials
===========

There are two ways to specify credentials.

Through `settings.py`::

    CRAWLERA_ENABLED = True
    CRAWLERA_APIKEY = 'apikey'

Through spider attributes::

    class MySpider:
        crawlera_enabled = True
        crawlera_apikey = 'apikey'

How to use it
=============

You just need to specify the headers when making a request like::

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
