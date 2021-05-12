.. _news:

Changes
=======

v2.0.0 (2021-05-NN)
-------------------

Following the upstream rebranding of Crawlera as Zyte Smart Proxy Manager,
``scrapy-crawlera`` has been renamed as ``scrapy-zyte-smartproxy``, with the
following backward-incompatible changes:

-   The repository name and Python Package Index (PyPI) name are now
    ``scrapy-zyte-smartproxy``.

-   Setting prefixes have switched from ``CRAWLERA_`` to ``ZYTE_SMARTPROXY_``.

-   Spider attribute prefixes and request meta key prefixes have switched from
    ``crawlera_`` to ``zyte_smartproxy_``.

-   ``scrapy_crawlera`` is now ``scrapy_zyte_smartproxy``.

-   ``CrawleraMiddleware`` is now ``ZyteSmartProxyMiddleware``, and its default
    ``url`` is now ``http://proxy.zyte.com:8011``.

-   Stat prefixes have switched from ``crawlera/`` to ``zyte_smartproxy/``.

-   The online documentation is moving to
    https://scrapy-zyte-smartproxy.readthedocs.io/

.. note:: Zyte Smart Proxy Manager headers continue to use the ``X-Crawlera-``
          prefix.

-   In addition to that, the ``X-Crawlera-Client`` header is now automatically
    included in all requests.

v1.7.2 (2020-12-01)
-------------------
- Use request.meta than response.meta in the middleware

v1.7.1 (2020-10-22)
-------------------
- Consider Crawlera response if contains `X-Crawlera-Version` header
- Build the documentation in Travis CI and fail on documentation issues
- Update matrix of tests

v1.7.0 (2020-04-01)
-------------------
- Added more stats to better understanding the internal states.
- Log warning when using `https://` protocol.
- Add default `http://` protocol in case of none provided, and log warning about it.
- Fix duplicated request when the response is not from crawlera, this was causing an
  infinite loop of retries when `dont_filter=True`.

v1.6.0 (2019-05-27)
-------------------

- Enable crawlera on demand by setting ``CRAWLERA_FORCE_ENABLE_ON_HTTP_CODES``

v1.5.1 (2019-05-21)
-------------------

- Remove username and password from settings since it's removed from crawlera.
- Include affected spider in logs.
- Handle situations when crawlera is restarted and reply with 407's for a few minutes
  by retrying the requests with a exponential backoff system.

v1.5.0 (2019-01-23)
-------------------

- Correctly check for bans in crawlera (Jobs will not get banned on non ban 503's).
- Exponential backoff when crawlera doesn't have proxies available.
- Fix ``dont_proxy=False`` header disabling crawlera when it is enabled.

v1.4.0 (2018-09-20)
-------------------

- Remove X-Crawlera-* headers when Crawlera is disabled.
- Introduction of DEFAULT_CRAWLERA_HEADERS settings.

v1.3.0 (2018-01-10)
-------------------

- Use CONNECT method to contact Crawlera proxy.

v1.2.4 (2017-07-04)
-------------------

- Trigger PYPI deployments after changes made to TOXENV in v1.2.3

v1.2.3 (2017-06-29)
-------------------

- Multiple documentation fixes
- Test scrapy-crawlera on combinations of software used by scrapinghub stacks


v1.2.2 (2017-01-19)
-------------------

- Fix Crawlera error stats key in Python 3.
- Add support for Python 3.6.


v1.2.1 (2016-10-17)
-------------------

- Fix release date in README.


v1.2.0 (2016-10-17)
-------------------

- Recommend middleware order to be ``610`` to run before ``RedirectMiddleware``.
- Change default download timeout to 190s or 3 minutes 10 seconds
  (instead of 1800s or 30 minutes).
- Test and advertize Python 3 compatiblity.
- New ``crawlera/request`` and ``crawlera/request/method/*`` stats counts.
- Clear Scrapy DNS cache for proxy URL in case of connection errors.
- Distribute plugin as universal wheel.
