# coding=utf-8

import re
import time
from collections import namedtuple
from functools import partial

import pycurl
import simplejson
import logging
from lxml import etree
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.concurrent import Future
from tornado.curl_httpclient import CurlAsyncHTTPClient
from tornado.httpclient import HTTPRequest, HTTPResponse, HTTPError
from tornado.httputil import HTTPHeaders
from tornado.options import options

from frontik.async import AsyncGroup
from frontik.auth import DEBUG_AUTH_HEADER_NAME
from frontik.compat import iteritems
from frontik.debug import DEBUG_HEADER_NAME, response_from_debug
from frontik.util import make_url, make_body, make_mfd


def _string_to_dict(s):
    return {name: value for (name, value) in (v.split('=') for v in s.split(' ') if v)}


http_logger = logging.getLogger('frontik.http_client')


class Server(object):
    @classmethod
    def from_config(cls, properties):
        params = {key: properties[key] for key in ('weight',) if key in properties}
        return cls(properties.get('server'), **params)

    def __init__(self, address, weight=1):
        self.address = address.rstrip(u'/')
        self.weight = int(weight)

        self.requests = 0
        self.fails = 0
        self.is_active = True

        self.stats_requests = 0
        self.stats_errors = 0

        if self.weight < 1:
            raise ValueError('weight should not be less then 1')

    def update(self, server):
        self.weight = server.weight

    def deactivate(self, timeout):
        self.is_active = False
        IOLoop.current().add_timeout(IOLoop.current().time() + timeout, self.restore)

    def restore(self):
        http_logger.info('restore server %s', self.address)
        self.fails = 0
        self.is_active = True


class Upstream(object):
    @staticmethod
    def parse_config(config):
        configs = [_string_to_dict(v) for v in config.split('|')]

        upstream_config = configs.pop(0)
        servers = [Server.from_config(server_config) for server_config in configs if server_config]

        return upstream_config, servers

    def __init__(self, name, config, servers):
        self.name = name
        self.servers = []
        self.tries = options.http_client_default_max_tries
        self.max_fails = options.http_client_default_max_fails
        self.fail_timeout = options.http_client_default_fail_timeout_sec
        self.last_index = 0

        self.update(config, servers)

    def borrow_server(self, exclude=None):
        min_load = 0
        min_index = None

        for i in range(len(self.servers)):
            index = (self.last_index + i) % len(self.servers)
            server = self.servers[index]

            if server is not None and server.is_active and (exclude is None or index not in exclude):
                load = server.requests / float(server.weight)
                if min_index is None or load < min_load:
                    min_load = load
                    min_index = index

        if min_index is None:
            return None, None

        self.last_index = min_index
        server = self.servers[self.last_index]
        server.requests += 1

        if options.http_client_stats_interval_ms != 0:
            server.stats_requests += 1

        return self.last_index, server.address

    def return_server(self, index, error=False):
        server = self.servers[index]
        if server is not None:
            if server.requests > 0:
                server.requests -= 1

            if error:
                server.fails += 1

                if options.http_client_stats_interval_ms != 0:
                    server.stats_errors += 1

                if self.max_fails != 0 and server.fails >= self.max_fails:
                    http_logger.info('disable server %s for upstream %s', server.address, self.name)
                    server.deactivate(self.fail_timeout)
            else:
                server.fails = 0

    def update(self, config, servers):
        if not servers:
            raise ValueError('server list should not be empty')

        self.tries = int(config.get('tries', self.tries))
        self.max_fails = int(config.get('max_fails', self.max_fails))
        self.fail_timeout = float(config.get('fail_timeout', self.fail_timeout))

        mapping = {server.address: server for server in servers}

        for index, server in enumerate(self.servers):
            changed = mapping.get(server.address)
            if changed is None:
                self.servers[index] = None
            else:
                del mapping[server.address]
                server.update(changed)

        for server in servers:
            if server.address in mapping:
                self._add_server(server)

    def _add_server(self, server):
        for index, s in enumerate(self.servers):
            if s is None:
                self.servers[index] = server
                return

        self.servers.append(server)

    def __str__(self):
        return '[{}]'.format(','.join(server.address for server in self.servers))


class BalancedHttpRequest(object):
    def __init__(self, host, upstream, uri, method='GET', data=None, headers=None, files=None, content_type=None,
                 connect_timeout=None, request_timeout=None, follow_redirects=True, idempotent=True):
        self.uri = uri if uri.startswith(u'/') else u'/' + uri
        self.upstream = upstream
        self.method = method
        self.headers = HTTPHeaders() if headers is None else HTTPHeaders(headers)
        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout
        self.follow_redirects = follow_redirects
        self.idempotent = idempotent
        self.body = None

        if self.connect_timeout is None:
            self.connect_timeout = options.http_client_default_connect_timeout
        if self.request_timeout is None:
            self.request_timeout = options.http_client_default_request_timeout

        self.connect_timeout *= options.timeout_multiplier
        self.request_timeout *= options.timeout_multiplier

        if self.method == 'POST':
            if files:
                self.body, content_type = make_mfd(data, files)
            else:
                self.body = make_body(data)

            if content_type is None:
                content_type = self.headers.get('Content-Type', 'application/x-www-form-urlencoded')

            self.headers['Content-Length'] = str(len(self.body))
        elif self.method == 'PUT':
            self.body = make_body(data)
        else:
            self.uri = make_url(self.uri, **({} if data is None else data))

        if content_type is not None:
            self.headers['Content-Type'] = content_type

        self.tries_left = self.upstream.tries if self.upstream is not None else options.http_client_default_max_tries
        self.request_time_left = self.request_timeout
        self.tried_hosts = None
        self.current_host = host.rstrip(u'/')
        self.current_fd = None

    def make_request(self):
        if self.upstream is not None:
            self.current_fd, self.current_host = self.upstream.borrow_server(self.tried_hosts)

        request = HTTPRequest(
            url=(self.current_host if self.backend_available() else self.upstream.name) + self.uri,
            body=self.body,
            method=self.method,
            headers=self.headers,
            follow_redirects=self.follow_redirects,
            connect_timeout=self.connect_timeout,
            request_timeout=self.request_time_left,
        )

        if options.http_proxy_host is not None:
            request.proxy_host = options.http_proxy_host
            request.proxy_port = options.http_proxy_port

        return request

    def backend_available(self):
        return self.current_host is not None

    def get_host(self):
        return self.upstream.name if self.upstream is not None else self.current_host

    def _check(self, response):
        # disable retries for not balancing backends
        if self.upstream is None:
            return False, False

        self.request_time_left -= response.request_time
        connect_error = response.code == 599 and 'HTTP 599: Failed to connect' in str(response.error)
        backend_failed = response.code in (503, 599)

        if self.tries_left <= 0 or not backend_failed or self.request_time_left <= 0:
            return False, backend_failed

        return connect_error or (self.idempotent and backend_failed), True

    def check_retry(self, response):
        self.tries_left -= 1

        do_retry, error = self._check(response)

        if self.upstream is not None and self.current_fd is not None:
            self.upstream.return_server(self.current_fd, error)

        if do_retry:
            http_logger.warn('got error from %s, retrying', self.current_host)

            if self.tried_hosts is None:
                self.tried_hosts = set()

            self.tried_hosts.add(self.current_fd)

        return do_retry


class HttpClientFactory(object):
    def __init__(self, tornado_http_client, upstreams):
        self.tornado_http_client = tornado_http_client
        self.upstreams = {}

        if options.http_client_stats_interval_ms != 0:
            PeriodicCallback(self.log_stats, options.http_client_stats_interval_ms).start()

        for name, upstream in iteritems(upstreams):
            self.register_upstream(name, upstream['config'], [Server.from_config(s) for s in upstream['servers']])

    def get_http_client(self, handler, modify_http_request_hook):
        return HttpClient(handler, self.tornado_http_client, modify_http_request_hook, self.upstreams)

    def update_upstream(self, name, config):
        if config is None:
            self.register_upstream(name, {}, [])
            return

        upstream_config, servers = Upstream.parse_config(config)
        self.register_upstream(name, upstream_config, servers)

    def register_upstream(self, name, upstream_config, servers):
        upstream = self.upstreams.get(name)

        if not servers:
            if upstream is not None:
                del self.upstreams[name]
                http_logger.info('delete %s upstream', name)
            return

        if upstream is None:
            upstream = Upstream(name, upstream_config, servers)
            self.upstreams[name] = upstream
            http_logger.info('add %s upstream: %s', name, str(upstream))
            return

        upstream.update(upstream_config, servers)
        http_logger.info('update %s upstream: %s', name, str(upstream))

    def log_stats(self):
        for name, upstream in iteritems(self.upstreams):
            info = []
            for server in upstream.servers:
                if server is None:
                    return

                info.append('{} : ({}, {} | {}, {}, {})'.format(
                    server.address, server.stats_requests, server.stats_errors, server.requests, server.weight,
                    'active' if server.is_active else 'dead'))
                server.stats_requests = 0
                server.stats_errors = 0

            http_logger.info('upstream %s servers: %s', name, ', '.join(info))


class HttpClient(object):
    def __init__(self, handler, http_client_impl, modify_http_request_hook, upstreams):
        self.handler = handler
        self.modify_http_request_hook = modify_http_request_hook
        self.http_client_impl = http_client_impl
        self.upstreams = upstreams

    def group(self, futures, callback=None, name=None):
        if callable(callback):
            results_holder = {}
            group_callback = self.handler.finish_group.add(self.handler.check_finished(callback, results_holder))

            async_group = AsyncGroup(group_callback, name=name)

            def future_callback(name, future):
                results_holder[name] = future.result()

            for name, future in iteritems(futures):
                if future.done():
                    future_callback(name, future)
                else:
                    self.handler.add_future(future, async_group.add(partial(future_callback, name)))

            async_group.try_finish_async()

        return futures

    def get_url(self, host, uri, data=None, headers=None, connect_timeout=None, request_timeout=None,
                callback=None, follow_redirects=True, add_to_finish_group=True,
                parse_response=True, parse_on_error=False):

        request = BalancedHttpRequest(host, self.upstreams.get(host), uri, 'GET', data, headers, None, None,
                                      connect_timeout, request_timeout, follow_redirects)

        return self._fetch_with_retry(request, callback, add_to_finish_group, parse_response, parse_on_error)

    def head_url(self, host, uri, data=None, headers=None, connect_timeout=None, request_timeout=None,
                 callback=None, follow_redirects=True, add_to_finish_group=True):

        request = BalancedHttpRequest(host, self.upstreams.get(host), uri, 'HEAD', data, headers, None, None,
                                      connect_timeout, request_timeout, follow_redirects)

        return self._fetch_with_retry(request, callback, add_to_finish_group, False, False)

    def post_url(self, host, uri, data='', headers=None, files=None, connect_timeout=None, request_timeout=None,
                 callback=None, follow_redirects=True, content_type=None, add_to_finish_group=True,
                 parse_response=True, parse_on_error=False):

        request = BalancedHttpRequest(host, self.upstreams.get(host), uri, 'POST', data, headers, files, content_type,
                                      connect_timeout, request_timeout, follow_redirects, False)

        return self._fetch_with_retry(request, callback, add_to_finish_group, parse_response, parse_on_error)

    def put_url(self, host, uri, data='', headers=None, connect_timeout=None, request_timeout=None,
                callback=None, content_type=None, add_to_finish_group=True,
                parse_response=True, parse_on_error=False):

        request = BalancedHttpRequest(host, self.upstreams.get(host), uri, 'PUT', data, headers, None, content_type,
                                      connect_timeout, request_timeout)

        return self._fetch_with_retry(request, callback, add_to_finish_group, parse_response, parse_on_error)

    def delete_url(self, host, uri, data=None, headers=None, connect_timeout=None, request_timeout=None,
                   callback=None, content_type=None, add_to_finish_group=True,
                   parse_response=True, parse_on_error=False):

        request = BalancedHttpRequest(host, self.upstreams.get(host), uri, 'DELETE', data, headers, None, content_type,
                                      connect_timeout, request_timeout)

        return self._fetch_with_retry(request, callback, add_to_finish_group, parse_response, parse_on_error)

    def _fetch_with_retry(self, request, callback, add_to_finish_group, parse_response, parse_on_error):
        future = Future()

        def request_finished_callback(response):
            if response is None:
                return

            if self.handler.is_finished():
                self.handler.log.warning('page was already finished, {} ignored'.format(callback))
                return

            result = self._parse_response(response, parse_response, parse_on_error)

            if callable(callback):
                callback(result.data, result.response)

            future.set_result(result)

        if add_to_finish_group:
            request_finished_callback = self.handler.finish_group.add(request_finished_callback)

        def retry_callback(response=None):
            if response is None:
                request_finished_callback(None)
                return

            if request.check_retry(response):
                self._fetch(request, retry_callback)
                return

            request_finished_callback(response)

        self._fetch(request, retry_callback)

        return future

    def _fetch(self, balanced_request, callback):
        if self.handler.is_finished():
            self.handler.log.warning(
                'attempted to make http request to %s %s when page is finished, ignoring',
                balanced_request.get_host(),
                balanced_request.uri
            )

            callback(None)
            return

        request = balanced_request.make_request()

        def request_callback(response):
            callback(self._log_response(request, response, balanced_request))

        if not balanced_request.backend_available():
            request_callback(
                HTTPResponse(request, 502,
                             error=HTTPError(502, 'No backend available for ' + balanced_request.get_host()),
                             request_time=0))
            return

        if self.handler.debug_mode.pass_debug:
            request.headers[DEBUG_HEADER_NAME] = 'true'

            # debug_timestamp is added to avoid caching of debug responses
            request.url = make_url(request.url, debug_timestamp=int(time.time()))

            for header_name in ('Authorization', DEBUG_AUTH_HEADER_NAME):
                authorization = self.handler.request.headers.get(header_name)
                if authorization is not None:
                    request.headers[header_name] = authorization

        request.headers['X-Request-Id'] = self.handler.request_id

        if isinstance(self.http_client_impl, CurlAsyncHTTPClient):
            request.prepare_curl_callback = partial(
                self._prepare_curl_callback, next_callback=request.prepare_curl_callback
            )

        self.http_client_impl.fetch(self.modify_http_request_hook(request, balanced_request), request_callback)

    def _prepare_curl_callback(self, curl, next_callback):
        curl.setopt(pycurl.NOSIGNAL, 1)

        if callable(next_callback):
            next_callback(curl)

    def _log_response(self, request, response, balanced_request):
        try:
            debug_extra = {}
            if response.headers.get(DEBUG_HEADER_NAME):
                debug_response = response_from_debug(request, response)
                if debug_response is not None:
                    debug_xml, response = debug_response
                    debug_extra['_debug_response'] = debug_xml

            if self.handler.debug_mode.enabled:
                retry = len(balanced_request.tried_hosts) if balanced_request.tried_hosts else 0
                debug_extra.update({'_response': response, '_request': request,
                                    '_request_retry': retry,
                                    '_balanced_request': balanced_request})

            log_message = 'got {code}{size} {url} in {time:.2f}ms'.format(
                code=response.code,
                url=response.effective_url,
                size=' {0} bytes'.format(len(response.body)) if response.body is not None else '',
                time=response.request_time * 1000
            )

            log_method = self.handler.log.warn if response.code >= 500 else self.handler.log.info
            log_method(log_message, extra=debug_extra)

        except Exception:
            self.handler.log.exception('Cannot log response info')

        return response

    def _parse_response(self, response, parse_response, parse_on_error):
        data = None
        result = RequestResult()

        try:
            if response.error and not parse_on_error:
                self._set_response_error(response)
            elif not parse_response:
                data = response.body
            elif response.code != 204:
                content_type = response.headers.get('Content-Type', '')
                for k, v in iteritems(DEFAULT_REQUEST_TYPES):
                    if k.search(content_type):
                        data = v(response, logger=self.handler.log)
                        break
        except FailedRequestException as ex:
            result.set_exception(ex)

        result.set(data, response)

        return result

    def _set_response_error(self, response):
        log_func = self.handler.log.error if response.code >= 500 else self.handler.log.warning
        log_func('{code} failed {url} ({reason!s})'.format(
            code=response.code, url=response.effective_url, reason=response.error)
        )

        raise FailedRequestException(reason=str(response.error), code=response.code)


class FailedRequestException(Exception):
    def __init__(self, **kwargs):
        self.attrs = kwargs


class RequestResult(object):
    __slots__ = ('data', 'response', 'exception')

    ResponseData = namedtuple('ResponseData', ('data', 'response'))

    def __init__(self):
        self.data = None
        self.response = None
        self.exception = None

    def set(self, data, response):
        self.data = data
        self.response = response

    def set_exception(self, exception):
        self.exception = exception


def _parse_response(response, logger, parser=None, response_type=None):
    try:
        return parser(response.body)
    except:
        _preview_len = 100

        if len(response.body) > _preview_len:
            body_preview = '{0}...'.format(response.body[:_preview_len])
        else:
            body_preview = response.body

        logger.exception('failed to parse {0} response from {1}, bad data: "{2}"'.format(
            response_type, response.effective_url, body_preview))

        raise FailedRequestException(url=response.effective_url, reason='invalid {0}'.format(response_type))


_xml_parser = etree.XMLParser(strip_cdata=False)
_parse_response_xml = partial(_parse_response,
                              parser=lambda x: etree.fromstring(x, parser=_xml_parser),
                              response_type='XML')

_parse_response_json = partial(_parse_response,
                               parser=simplejson.loads,
                               response_type='JSON')

DEFAULT_REQUEST_TYPES = {
    re.compile('.*xml.?'): _parse_response_xml,
    re.compile('.*json.?'): _parse_response_json,
    re.compile('.*text/plain.?'): (lambda response, logger: response.body),
}