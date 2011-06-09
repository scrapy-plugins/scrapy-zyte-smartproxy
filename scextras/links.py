from scrapy.http import Request

def follow_links(link_extractor, response, callback):
    """Returns a generator of requests with given `callback`
    of links extractor from `response`.

    Parameters:
        link_extractor -- LinkExtractor to use
        response -- Response to extract links from
        callback -- callback to apply to each new requests

    """
    for link in link_extractor.extract_links(response):
        yield Request(link.url, callback=callback)
