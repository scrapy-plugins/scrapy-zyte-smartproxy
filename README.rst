===============
scrapy-crawlera
===============

.. image:: https://badge.fury.io/py/scrapy-crawlera.png
   :target: http://badge.fury.io/py/scrapy-crawlera

.. image:: https://secure.travis-ci.org/scrapy-plugins/scrapy-crawlera.png?branch=master
   :target: http://travis-ci.org/scrapy-plugins/scrapy-crawlera

scrapy-crawlera provides easy use of `Crawlera <http://scrapinghub.com/crawlera>`_ with Scrapy.

Installation
============

You can install scrapy-crawlera using pip::

    pip install scrapy-crawlera

You can then enable the middleware in your `settings.py`::

    DOWNLOADER_MIDDLEWARES = {
        ...
        'scrapy_crawlera.CrawleraMiddleware': 600
    }


Credentials
===========

There are two ways to specify credentials. 

Through `settings.py`::

    CRAWLERA_ENABLED = True
    CRAWLERA_USER = 'username'
    CRAWLERA_PASS = 'password'

Through spider attributes::

    class MySpider:
        crawlera_enabled = True
        crawlera_user = 'username'
        crawlera_pass = 'password'

You got an APIKEY? Replace `CRAWLERA_USER` with it::

    CRAWLERA_USER = 'APIKEY'
    CRAWLERA_PASS = ''

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
