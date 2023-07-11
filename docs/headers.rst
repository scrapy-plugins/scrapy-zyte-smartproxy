Headers
=======

The Zyte proxy API services that you can use with this downloader middleware
each support a different set of HTTP request and response headers that give
you access to additional features. You can find more information about those
headers in the documentation of each service, `Zyte API’s <zyte-api-headers>`_
and `Zyte Smart Proxy Manager’s <spm-headers>`_.

.. _zyte-api-headers: https://example.com
.. _spm-headers: https://docs.zyte.com/smart-proxy-manager.html#request-headers

If you try to use a header for one service while using the other service, this
downloader middleware will try to translate your header into the right header
for the target service and, regardless of whether or not translation was done,
the original header will be dropped.

Also, response headers that can be translated will be always translated,
without dropping the original header, so code expecting a response header from
one service can work even if a different service was used.

Translation is supported for the following headers:

========================= ===========================
Zyte API                  Zyte Smart Proxy Manager
========================= ===========================
``Zyte-Client``           ``X-Crawlera-Client``
``Zyte-Device``           ``X-Crawlera-Profile``
``Zyte-Error``            ``X-Crawlera-Error``
``Zyte-Geolocation``      ``X-Crawlera-Region``
``Zyte-JobId``            ``X-Crawlera-JobId``
``Zyte-No-Bancheck``      ``X-Crawlera-No-Bancheck``
``Zyte-Override-Headers`` ``X-Crawlera-Profile-Pass``
``Zyte-Session-ID``       ``X-Crawlera-Session``
========================= ===========================

Also, if a request is not being proxied and includes a header for any of these
services, it will be dropped, to prevent leaking data to external websites.
This downloader middleware assumes that a header prefixed with ``Zyte-`` is a
Zyte API header, and that a header prefixed with ``X-Crawlera-`` is a Zyte
Smart Proxy Manager header, even if they are not known headers otherwise.

When dropping a header, be it as part of header translation or to avoid leaking
data, a warning message with details will be logged.
