import pytest
from scrapy import Spider as _Spider
from scrapy.http import Response, Request
from scrapy.item import Item
from scrapy.utils.reqser import request_to_dict
from scrapy.utils.test import get_crawler

from scrapy_crawlera.spidermiddlewares import CrawleraSessionReuseMiddleware


SESSION = '1'


def compare_requests(request1, request2):
    assert request_to_dict(request1) == request_to_dict(request2)


def process_output(response, result, settings=None):
    crawler = get_crawler(Spider, settings)
    mw = CrawleraSessionReuseMiddleware.from_crawler(crawler)
    generator = mw.process_spider_output(response, [result], Spider())
    return list(generator)[0]


def get_request(reuse=False, session=None):
    headers = {}
    if reuse is True:
        assert session is None
        headers['X-Crawlera-Session'] = '_reuse'
    elif session is not None:
        headers['X-Crawlera-Session'] = session
    return Request('https://example.com', headers=headers)


def get_response(session=None, error=None):
    headers = {}
    if session is not None:
        headers['X-Crawlera-Session'] = session
    if error is not None:
        headers['X-Crawlera-Error'] = error
    return Response('https://example.com', headers=headers)


class Spider(_Spider):
    name = 'spider'


@pytest.mark.parametrize(
    'item',
    [
        (
            {},
        ),
        (
            Item(),
        ),
    ]
)
def test_item(item):
    response = get_response(session=SESSION)
    assert process_output(response, item) == item


def test_no_session():
    response = get_response()
    input_request = get_request()
    processed_request = process_output(response, input_request)
    expected_request = get_request()
    compare_requests(processed_request, expected_request)


def test_bad_session_id():
    response = get_response(session=SESSION, error='bad_session_id')
    input_request = get_request(reuse=True)
    processed_request = process_output(response, input_request)
    expected_request = get_request()
    compare_requests(processed_request, expected_request)


def test_bad_session_id_default_session():
    response = get_response(session=SESSION, error='bad_session_id')
    input_request = get_request(reuse=True)
    settings = {'CRAWLERA_SESSION_REUSE_DEFAULT_SESSION': 'create'}
    processed_request = process_output(response, input_request, settings)
    expected_request = get_request(session='create')
    compare_requests(processed_request, expected_request)


def test_user_session_limit():
    # This session error is only expected to come from a response that has no
    # ``X-Crawlera-Session`` value, caused by a request with ``create`` as
    # ``X-Crawlera-Session`` value.
    response = get_response(error='user_session_limit')
    input_request = get_request(reuse=True)
    processed_request = process_output(response, input_request)
    expected_request = get_request()
    compare_requests(processed_request, expected_request)


@pytest.mark.parametrize(
    'error',
    [
        # https://doc.scrapinghub.com/crawlera.html#errors
        (
            'bad_proxy_auth',
        ),
        (
            'too_many_conns',
        ),
        (
            'header_auth',
        ),
        (
            '',
        ),
        (
            'nxdomain',
        ),
        (
            'ehostunreach',
        ),
        (
            'econnrefused',
        ),
        (
            'econnreset',
        ),
        (
            'socket_closed_remotely',
        ),
        (
            'client_conn_closed',
        ),
        (
            'noslaves',
        ),
        (
            'banned',
        ),
        (
            'serverbusy',
        ),
        (
            'timeout',
        ),
        (
            'msgtimeout',
        ),
        (
            'domain_forbidden',
        ),
        (
            'bad_header',
        ),
        (
            'data_error',
        ),
    ]
)
def test_non_session_error(error):
    session = SESSION
    response = get_response(session=session, error=error)
    input_request = get_request(reuse=True)
    processed_request = process_output(response, input_request)
    expected_request = get_request(session=SESSION)
    compare_requests(processed_request, expected_request)


def test_session():
    session = SESSION
    response = get_response(session=session)
    input_request = get_request(reuse=True)
    processed_request = process_output(response, input_request)
    expected_request = get_request(session=SESSION)
    compare_requests(processed_request, expected_request)


def test_create_on_sessionless_reuse():
    response = get_response()
    input_request = get_request(reuse=True)
    settings = {'CRAWLERA_SESSION_REUSE_DEFAULT_SESSION': 'create'}
    processed_request = process_output(response, input_request, settings)
    expected_request = get_request(session='create')
    compare_requests(processed_request, expected_request)


def test_dont_create_on_sessionless_reuse():
    response = get_response()
    input_request = get_request(reuse=True)
    processed_request = process_output(response, input_request)
    expected_request = get_request()
    compare_requests(processed_request, expected_request)


@pytest.mark.parametrize(
    'session',
    [
        (
            SESSION,
        ),
        (
            'create',
        ),
    ]
)
def test_header_without_reuse(session):
    response = get_response()
    input_request = get_request(session=session)
    processed_request = process_output(response, input_request)
    expected_request = get_request(session=session)
    compare_requests(processed_request, expected_request)
