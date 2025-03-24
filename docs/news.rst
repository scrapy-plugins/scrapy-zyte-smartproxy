.. _news:

Changes
=======

v2.4.1 (2025-03-24)
-------------------

Stop expecting a ``Zyte-Error`` header in responses from `Zyte API`_ `proxy
mode`_, it is named ``Zyte-Error-Type``.

v2.4.0 (2024-12-30)
-------------------

Removed official support for Python 3.4, 3.5, 3.6, 3.7 and 3.8. Added official
Python 3.13 support.

`Backward-compatible
<https://docs.zyte.com/zyte-api/migration/zyte/smartproxy.html#spm-migrate-map>`__
``X-Crawlera``-prefixed headers are no longer translated into their matching
`Zyte API proxy mode headers
<https://docs.zyte.com/zyte-api/usage/proxy-mode.html#zapi-proxy-headers>`_,
Zyte API now handles their translation on the server side.

Added a new ``ZYTE_SMARTPROXY_KEEP_HEADERS`` setting that allows disabling
header dropping and translation.

v2.3.5 (2024-08-05)
-------------------

Ban and throttling responses from `Zyte API`_ `proxy mode`_ are now handled in
line with matching responses from Zyte Smart Proxy Manager.

v2.3.4 (2024-05-09)
-------------------

`Zyte API`_ `proxy mode`_ now has its own stat prefix.

Some user-facing messages mentioning only Zyte Smart Proxy Manager have also
been updated to reflect the fact that scrapy-zyte-smartproxy also supports Zyte
API proxy mode.

v2.3.3 (2024-02-22)
-------------------

Fix response handling for `Zyte API`_ `proxy mode`_. Before, a single
connection issue during a request would add a 90 second delay between requests
until the end of the crawl, instead of removing the delay after the first
successful response.

v2.3.2 (2024-02-14)
-------------------

Detect scenarios where the ``proxy`` ``Request.meta`` key has probably been
accidentally copied from an earlier response, warn about it, and fix the value.

The ``Zyte-Client`` header is again sent when using `Zyte API`_ `proxy mode`_,
now that Zyte API supports it.

v2.3.1 (2023-11-20)
-------------------

Fixed `Zyte API`_ `proxy mode`_ support by removing the mapping of unsupported
headers ``Zyte-Client`` and ``Zyte-No-Bancheck``.

v2.3.0 (2023-10-20)
-------------------

Added support for the upcoming `proxy mode`_ of `Zyte API`_.

.. _proxy mode: https://docs.zyte.com/zyte-api/usage/proxy-mode.html
.. _Zyte API: https://docs.zyte.com/zyte-api/get-started.html

Added a BSD-3-Clause license file.

v2.2.0 (2022-08-05)
-------------------

Added support for Scrapy 2.6.2 and later.

Scrapy 1.4 became the minimum supported Scrapy version.

v2.1.0 (2021-06-16)
-------------------

- Use a custom logger instead of the root one

v2.0.0 (2021-05-12)
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
