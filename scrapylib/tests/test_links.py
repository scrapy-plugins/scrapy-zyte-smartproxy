import unittest
from scrapylib.links import follow_links
from scrapy.http import Request

class LinkMock(object):
    def __init__(self, url):
        self.url = url

class LinkExtractorMock(object):
    def extract_links(self, response):
        return [LinkMock(url=x) for x in response.split(':')]

def some_callback():
    pass

class TestLinks(unittest.TestCase):

    def test_follow_links(self):
        r = list(follow_links(LinkExtractorMock(), 'link1:link2:link3', callback=some_callback))
        assert all(isinstance(x, Request) for x in r)
        assert all(x.callback is some_callback for x in r)
        self.assertEqual([x.url for x in r], ['link1', 'link2', 'link3'])
