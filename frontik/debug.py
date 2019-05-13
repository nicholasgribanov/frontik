import base64
import inspect
import json
import logging
import os
import pprint
import re
import time
import traceback
from binascii import crc32
from http.cookies import SimpleCookie
from io import BytesIO
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import jinja2
from lxml import etree
from tornado.escape import to_unicode, utf8
from tornado.httpclient import HTTPResponse
from tornado.httputil import HTTPHeaders
from tornado.web import OutputTransform

from frontik import media_types, request_context
from frontik.loggers import BufferedHandler
from frontik.util import _decode_bytes_from_charset, any_to_unicode, get_cookie_or_url_param_value

DEBUG_HEADER_NAME = 'x-hh-debug'

debug_log = logging.getLogger('frontik.debug')


def response_from_debug(request, response):
    debug_response = json.loads(response.body)
    original_response = debug_response.get('original_response')

    if original_response is not None:
        original_buffer = base64.b64decode(original_response.get('buffer', ''))

        headers = HTTPHeaders(response.headers)
        headers.update(original_response.get('headers', {}))

        fake_response = HTTPResponse(
            request,
            int(original_response.get('code', 599)),
            headers=headers,
            buffer=BytesIO(original_buffer),
            effective_url=response.effective_url,
            request_time=response.request_time,
            time_info=response.time_info
        )

        return debug_response, fake_response

    return None


def _response_to_json(response):
    content_type = response.headers.get('Content-Type', '')
    content_type_class = ''

    if 'charset' in content_type:
        charset = content_type.partition('=')[-1]
    else:
        charset = 'utf-8'

    try_charsets = (charset, 'cp1251')

    try:
        if not response.body:
            body = ''
        elif 'text/html' in content_type:
            content_type_class = 'html'
            body = _decode_bytes_from_charset(response.body, try_charsets)
        elif 'protobuf' in content_type:
            body = repr(response.body)
        elif 'xml' in content_type:
            content_type_class = 'xml'
            body = _pretty_print_xml(etree.fromstring(response.body))
        elif 'json' in content_type:
            content_type_class = 'javascript'
            body = _pretty_print_json(json.loads(response.body))
        else:
            if 'javascript' in content_type:
                content_type_class = 'javascript'
            body = _decode_bytes_from_charset(response.body, try_charsets)

    except Exception:
        debug_log.exception('cannot parse response body')
        body = repr(response.body)

    time_info = {}
    try:
        for name, value in response.time_info.items():
            time_info[name] = f'{value * 1000} ms'
    except Exception:
        debug_log.exception('cannot append time info')

    return {
        'content_type_class': content_type_class,
        'body': body,
        'code': response.code,
        'error': str(response.error) if response.error else None,
        'size': len(response.body) if response.body is not None else 0,
        'request_time': int(response.request_time * 1000),
        'headers': _headers_to_json(response.headers),
        'cookies': _cookies_to_json(response.headers),
        'time_info': time_info,
    }


def _request_to_json(request):
    content_type = request.headers.get('Content-Type', '')
    body = None

    if request.body:
        try:
            if 'json' in content_type:
                body = _pretty_print_json(json.loads(request.body))
            elif 'protobuf' in content_type:
                body = repr(request.body)
            else:
                body = {}
                body_query = parse_qs(request.body, True)
                for name, values in body_query.items():
                    for value in values:
                        body[to_unicode(name)] = to_unicode(value)
        except Exception:
            debug_log.exception('cannot parse request body')
            body = repr(request.body)

    return {
        'content_type': content_type,
        'body': body,
        'start_time': request.start_time,
        'method': request.method,
        'url': request.url,
        'query_params': _query_params_to_json(request.url),
        'headers': _headers_to_json(request.headers),
        'cookies': _cookies_to_json(request.headers),
        'curl': _request_to_curl_string(request)
    }


def _balanced_request_to_json(balanced_request, retry, rack, datacenter):
    info = {}

    if balanced_request.upstream.balanced:
        upstream_name = balanced_request.upstream.name.upper()
        info['upstream'] = {
            'name': upstream_name,
            'color': _string_to_color(upstream_name),
            'server': {
                'rack': rack,
                'datacenter': datacenter
            }
        }

    if retry > 0:
        info['retry'] = retry

    return info


def _request_to_curl_string(request):
    def _escape_apos(string):
        return string.replace("'", "'\"'\"'")

    try:
        request_body = _escape_apos(request.body.decode('ascii')) if request.body else None
        is_binary_body = False
    except UnicodeError:
        request_body = repr(request.body).strip('b')
        is_binary_body = True

    curl_headers = HTTPHeaders(request.headers)
    if request.body and 'Content-Length' not in curl_headers:
        curl_headers['Content-Length'] = str(len(request.body))

    if is_binary_body:
        curl_echo_data = f'echo -e {request_body} |'
        curl_data_string = '--data-binary @-'
    else:
        curl_echo_data = ''
        curl_data_string = f"--data '{request_body}'" if request_body else ''

    def _format_header(key):
        header_value = any_to_unicode(curl_headers[key])
        return f"-H '{key}: {_escape_apos(header_value)}'"

    return "{echo} curl -X {method} '{url}' {headers} {data}".format(
        echo=curl_echo_data,
        method=request.method,
        url=to_unicode(request.url),
        headers=' '.join(_format_header(k) for k in sorted(curl_headers.keys())),
        data=curl_data_string
    ).strip()


def _get_query_parameters(url):
    url = 'http://' + url if not re.match(r'[a-z]+://.+\??.*', url, re.IGNORECASE) else url
    return parse_qs(urlparse(url).query, True)


def _query_params_to_json(url):
    params = []
    query = _get_query_parameters(url)
    for name, values in query.items():
        for value in values:
            try:
                params.append((to_unicode(name), to_unicode(value)))
            except UnicodeDecodeError:
                debug_log.exception('cannot decode parameter name or value')
                params.append((repr(name), repr(value)))

    return params


def _headers_to_json(request_or_response_headers: HTTPHeaders):
    headers = []
    for name, value in request_or_response_headers.items():
        if name != 'Cookie':
            headers.append((name, to_unicode(value)))

    return headers


def _cookies_to_json(request_or_response_headers: HTTPHeaders):
    cookies = []
    if 'Cookie' in request_or_response_headers:
        _cookies = SimpleCookie(request_or_response_headers['Cookie'])
        for cookie in _cookies:
            cookies.append((cookie, _cookies[cookie].value))

    return cookies


def _exception_to_json(exc_info):
    exception = {
        'text': ''.join(map(to_unicode, traceback.format_exception(*exc_info)))
    }

    try:
        trace_items = []
        trace = exc_info[2]
        while trace:
            frame = trace.tb_frame
            trace_step = {
                'file': inspect.getfile(frame),
                'locals': pprint.pformat(frame.f_locals)
            }

            try:
                lines, starting_line = inspect.getsourcelines(frame)
            except IOError:
                lines, starting_line = [], None

            trace_lines = []
            for i, l in enumerate(lines):
                line = {
                    'text': l,
                    'number': starting_line + i
                }

                if starting_line + i == frame.f_lineno:
                    line['selected'] = True

                trace_lines.append(line)

            trace_step['lines'] = trace_lines
            trace_items.append(trace_step)
            trace = trace.tb_next

        exception['trace'] = trace_items
    except Exception:
        debug_log.exception('cannot add traceback lines')

    return exception


def _xslt_profile_to_json(profile):
    attrs = ('match', 'name', 'mode', 'calls', 'time', 'average')
    templates = [{attr: tpl.get(attr) for attr in attrs} for tpl in profile]

    return {
        'templates': templates,
        'total_time': sum(float(tpl['time']) for tpl in templates)
    }


def _pretty_print_xml(node):
    return etree.tostring(node, pretty_print=True, encoding='unicode')


def _pretty_print_json(node):
    return json.dumps(node, sort_keys=True, indent=2, ensure_ascii=False)


def _string_to_color(value):
    value_hash = crc32(utf8(value)) % 0xffffffff
    return '#%02x%02x%02x' % ((value_hash & 0xFF0000) >> 16, (value_hash & 0x00FF00) >> 8, value_hash & 0x0000FF)


def _generate_id():
    return uuid4().hex


class DebugHandler(BufferedHandler):
    FIELDS = ('created', 'filename', 'funcName', 'levelname', 'lineno', 'module', 'msecs',
              'name', 'pathname', 'process', 'relativeCreated', 'threadName')

    def __init__(self, request_start_time):
        self.request_start_time = request_start_time
        super().__init__()

    def produce_all(self):
        return [self._produce_one(record) for record in self.records]

    def _produce_one(self, record):
        entry = {}
        for field in self.FIELDS:
            entry[field] = getattr(record, field, None)

        entry['msg'] = record.getMessage()

        if record.exc_info is not None:
            entry['exception'] = _exception_to_json(record.exc_info)

        if getattr(record, '_response', None) is not None:
            entry['response'] = _response_to_json(record._response)

        if getattr(record, '_request', None) is not None:
            entry['request'] = _request_to_json(record._request)

        if getattr(record, '_balanced_request', None) is not None:
            entry['balanced_request'] = _balanced_request_to_json(
                record._balanced_request, record._request_retry, record._rack, record._datacenter
            )

        if getattr(record, '_debug_response', None) is not None:
            entry['debug_response'] = record._debug_response

        if getattr(record, '_xslt_profile', None) is not None:
            entry['xslt_profile'] = _xslt_profile_to_json(record._xslt_profile)

        if getattr(record, '_xml', None) is not None:
            entry['xml'] = etree.tostring(record._xml, encoding='unicode', pretty_print=True)

        if getattr(record, '_protobuf', None) is not None:
            entry['protobuf'] = str(record._protobuf)

        if getattr(record, '_text', None) is not None:
            entry['text'] = record._text

        return entry


class DebugTransform(OutputTransform):
    _JINJA_ENV = jinja2.Environment(
        auto_reload=False, autoescape=True, cache_size=0,
        loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'debug')),
    )

    _DEBUG_TEMPLATE = _JINJA_ENV.get_template('debug.html')

    def __init__(self, application, request):
        super().__init__(request)

        self.application = application
        self.request = request
        self.status_code = None
        self.headers = None
        self.chunks = None

    def is_enabled(self):
        return getattr(self.request, '_debug_enabled', False)

    def is_inherited(self):
        return getattr(self.request, '_debug_inherited', False)

    def transform_first_chunk(self, status_code, headers: HTTPHeaders, chunk, finishing):
        if not self.is_enabled():
            return status_code, headers, chunk

        self.status_code = status_code
        self.headers = headers
        self.chunks = [chunk]

        if not self.is_inherited():
            headers = HTTPHeaders({'Content-Type': media_types.TEXT_HTML})
        else:
            headers = HTTPHeaders({
                'Content-Type': media_types.APPLICATION_JSON,
                DEBUG_HEADER_NAME: 'true'
            })

        return 200, headers, self.produce_debug_body(finishing)

    def transform_chunk(self, chunk, finishing):
        if not self.is_enabled():
            return chunk

        self.chunks.append(chunk)

        return self.produce_debug_body(finishing)

    def produce_debug_body(self, finishing):
        if not finishing:
            return b''

        start_time = time.time()
        response_buffer = b''.join(self.chunks)

        debug_data = {
            'request_id': request_context.get_request_id(),
            'handler_name': request_context.get_handler_name(),
            'start_time': self.request._start_time,
            'total_time': int((time.time() - self.request._start_time) * 1000),
            'request': {
                'method': self.request.method,
                'query_params': _query_params_to_json(self.request.uri),
                'headers': _headers_to_json(self.request.headers),
                'cookies': _cookies_to_json(self.request.headers)
            },
            'response': {
                'headers': _headers_to_json(self.headers),
                'cookies': _cookies_to_json(self.headers)
            },
            'response_size': len(response_buffer),
            'original_response': {
                'buffer': to_unicode(base64.b64encode(response_buffer)),
                'headers': dict(self.headers),
                'code': int(self.status_code)
            }
        }

        try:
            debug_data['versions'] = self.application.get_versions()
        except Exception:
            debug_log.exception('cannot add version information')
            debug_data['versions'] = 'exception occured: see logs for details'

        try:
            debug_data['status'] = self.application.get_current_status()
        except Exception:
            debug_log.exception('cannot add status information')
            debug_data['status'] = 'exception occured: see logs for details'

        log_entries = request_context.get_log_handler().produce_all()
        debug_data['log_entries'] = log_entries
        debug_data['total_requests'] = len([e for e in log_entries if 'request' in e])
        debug_data['total_bytes_received'] = sum(e.get('response', {}).get('size', 0) for e in log_entries)
        debug_data['generation_time'] = int((time.time() - start_time) * 1000)

        if not getattr(self.request, '_debug_inherited', False):
            try:
                return utf8(self._DEBUG_TEMPLATE.render(generate_id=_generate_id, debug_response=debug_data))
            except Exception:
                debug_log.exception('debug template error')

        return utf8(json.dumps(debug_data))


class DebugMode:
    def __init__(self, handler):
        debug_value = get_cookie_or_url_param_value(handler, 'debug')

        self.mode_values = debug_value.split(',') if debug_value is not None else ''
        self.inherited = handler.request.headers.get(DEBUG_HEADER_NAME)

        if self.inherited:
            debug_log.debug('debug mode is inherited due to %s request header', DEBUG_HEADER_NAME)
            handler.request._debug_inherited = True

        if debug_value is not None or self.inherited:
            handler.require_debug_access()

            self.enabled = handler.request._debug_enabled = True
            self.pass_debug = 'nopass' not in self.mode_values or self.inherited
            self.profile_xslt = 'xslt' in self.mode_values

            request_context.set_log_handler(DebugHandler(handler.request._start_time))

            if self.pass_debug:
                debug_log.debug('%s header will be passed to all requests', DEBUG_HEADER_NAME)
        else:
            self.enabled = False
            self.pass_debug = False
            self.profile_xslt = False
