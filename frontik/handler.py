import asyncio
import enum
import http.client
import logging
import time
from asyncio import Future
from bisect import bisect
from functools import wraps
from typing import TYPE_CHECKING

import tornado.curl_httpclient
import tornado.web
from tornado.httputil import HTTPHeaders
from tornado.options import options
from tornado.web import RequestHandler

import frontik.auth
import frontik.handler_active_limit
from frontik import media_types, request_context
from frontik.auth import DEBUG_AUTH_HEADER_NAME
from frontik.debug import DEBUG_HEADER_NAME, DebugMode
from frontik.http_client import FailFastError, ParseMode, RequestResult
from frontik.preprocessors import _get_preprocessors, _unwrap_preprocessors
from frontik.renderers import GenericRenderer, Renderer
from frontik.util import _decode_bytes_from_charset, make_url
from frontik.version import version as frontik_version

if TYPE_CHECKING:  # pragma: no cover
    from types import MethodType, TracebackType
    from typing import Any, Callable, Coroutine, List, Optional, Tuple, Type

    from aiokafka import AIOKafkaProducer
    from consul.aio import Consul
    from tornado.httputil import HTTPServerRequest

    from frontik.app import FrontikApplication
    from frontik.http_client import BalancedHttpRequest, HttpClient
    from frontik.integrations.sentry import SentryLogger
    from frontik.integrations.statsd import StatsdClientWithTags

    RenderPostprocessor = Callable[['PageHandler', str], Coroutine[None, None, None]]
    Postprocessor = Callable[['PageHandler'], Coroutine[None, None, None]]

    ExceptionType = Optional[Type[BaseException]]
    ExceptionInstance = Optional[BaseException]
    TracebackInstance = Optional[TracebackType]
    ExceptionHook = Callable[[ExceptionType, ExceptionInstance, TracebackInstance], None]


def _fallback_status_code(status_code):
    return status_code if status_code in http.client.responses else http.client.SERVICE_UNAVAILABLE


class AbortPage(Exception):
    pass


class FinishWithPostprocessors(Exception):
    def __init__(self, wait_handler=False):
        super().__init__()
        self.wait_handler = wait_handler


class HTTPErrorWithPostprocessors(tornado.web.HTTPError):
    pass


handler_logger = logging.getLogger('handler')


class RendererPriority(enum.IntEnum):
    JINJA = XSLT = 1
    GENERIC = 2
    JSON = 3
    XML = 4


class PageHandler(RequestHandler):

    preprocessors = ()

    def __init__(self, application: 'FrontikApplication', request: 'HTTPServerRequest', **kwargs):
        self.name = self.__class__.__name__
        self.request_id = request_context.get_request_id()
        self.config = application.config
        self.log = handler_logger

        self.text = None
        self.renderers = []  # type: List[Tuple[int, Renderer]]
        self.register_renderer(GenericRenderer(self), RendererPriority.GENERIC)

        super().__init__(application, request, **kwargs)

        self._execute_coroutine = None
        self._handler_futures = []  # type: List[Future]
        self._preprocessor_futures = []  # type: List[Future]
        self._exception_hooks = []  # type: List[ExceptionHook]

        for integration in application.integrations:
            integration.initialize_handler(self)

        self._debug_access = None  # type: Optional[bool]
        self._render_postprocessors = []  # type: List[RenderPostprocessor]
        self._postprocessors = []  # type: List[Postprocessor]

    def __repr__(self):
        return '.'.join([self.__module__, self.__class__.__name__])

    def prepare(self):
        self.active_limit = frontik.handler_active_limit.ActiveHandlersLimit(self.get_statsd_client())
        self.debug_mode = DebugMode(self)

        self._http_client = self.application.http_client_factory.get_http_client(
            self, self.modify_http_client_request
        )  # type: HttpClient

        return super().prepare()

    def require_debug_access(self, login: str = None, passwd: str = None) -> None:
        if self._debug_access is None:
            if options.debug:
                debug_access = True
            else:
                check_login = login if login is not None else options.debug_login
                check_passwd = passwd if passwd is not None else options.debug_password
                frontik.auth.check_debug_auth(self, check_login, check_passwd)
                debug_access = True

            self._debug_access = debug_access

    def set_default_headers(self) -> None:
        self._headers = HTTPHeaders({
            'Server': f'Frontik/{frontik_version}',
            'X-Request-Id': self.request_id,
        })

    def decode_argument(self, value: bytes, name: str = None):
        try:
            return super().decode_argument(value, name)
        except (UnicodeError, tornado.web.HTTPError):
            self.log.warning('cannot decode utf-8 query parameter, trying other charsets')

        try:
            return _decode_bytes_from_charset(value)
        except UnicodeError:
            self.log.exception('cannot decode argument, ignoring invalid chars')
            return value.decode('utf-8', 'ignore')

    def set_status(self, status_code, reason=None):
        status_code = _fallback_status_code(status_code)
        super().set_status(status_code, reason=reason)

    def redirect(self, url, *args, **kwargs):
        self.log.info('redirecting to: %s', url)
        return super().redirect(url, *args, **kwargs)

    def reverse_url(self, name, *args, **kwargs):
        return self.application.reverse_url(name, *args, **kwargs)

    def wait_future(self, future: Future):
        if self._handler_futures is None:
            raise Exception('handler is already finished, calling wait_future at this time is incorrect')

        self._handler_futures.append(future)
        return future

    def wait_callback(self, callback):
        future = Future()

        @wraps(callback)
        def wait_wrapper(*args, **kwargs):
            future.set_result(None)
            return callback(*args, **kwargs)

        future.add_done_callback(wait_wrapper)
        self.wait_future(future)
        return wait_wrapper

    # Requests handling

    def _execute(self, transforms, *args, **kwargs):
        self._auto_finish = False
        request_context.set_handler_name(repr(self))
        return super()._execute(transforms, *args, **kwargs)

    def get(self, *args, **kwargs):
        self._execute_coroutine = self._execute_page(self.get_page)
        asyncio.create_task(self._execute_coroutine)

    def post(self, *args, **kwargs):
        self._execute_coroutine = self._execute_page(self.post_page)
        asyncio.create_task(self._execute_coroutine)

    def head(self, *args, **kwargs):
        self._execute_coroutine = self._execute_page(self.get_page)
        asyncio.create_task(self._execute_coroutine)

    def delete(self, *args, **kwargs):
        self._execute_coroutine = self._execute_page(self.delete_page)
        asyncio.create_task(self._execute_coroutine)

    def put(self, *args, **kwargs):
        self._execute_coroutine = self._execute_page(self.put_page)
        asyncio.create_task(self._execute_coroutine)

    def options(self, *args, **kwargs):
        self.__return_405()

    async def _execute_page(self, page_handler_method: 'MethodType'):
        try:
            preprocessors = _unwrap_preprocessors(self.preprocessors) + _get_preprocessors(page_handler_method.__func__)
            preprocessors_completed = await self._run_preprocessors(preprocessors)

            if not preprocessors_completed:
                self.log.info('page was already finished, skipping page method')
                return

            await page_handler_method()

            await self._wait_handler_futures()

            await self._postprocess()

        except Exception as e:
            try:
                self._handle_request_exception(e)
            except Exception:
                self.log.exception('exception in exception handler')

    async def _wait_handler_futures(self):
        while self._handler_futures:
            futures = self._handler_futures[:]
            self._handler_futures = []
            await asyncio.gather(*futures)

        self._handler_futures = None

    async def get_page(self):
        """ This method can be implemented in the subclass """
        await self.__return_405()

    async def post_page(self):
        """ This method can be implemented in the subclass """
        await self.__return_405()

    async def put_page(self):
        """ This method can be implemented in the subclass """
        await self.__return_405()

    async def delete_page(self):
        """ This method can be implemented in the subclass """
        await self.__return_405()

    def __return_405(self):
        allowed_methods = [
            name for name in ('get', 'post', 'put', 'delete') if f'{name}_page' in vars(self.__class__)
        ]
        self.set_header('Allow', ', '.join(allowed_methods))
        self.set_status(405)
        return self.finish()

    def get_page_fail_fast(self, request_result: RequestResult):
        self.__return_error(request_result.response.code)

    def post_page_fail_fast(self, request_result: RequestResult):
        self.__return_error(request_result.response.code)

    def put_page_fail_fast(self, request_result: RequestResult):
        self.__return_error(request_result.response.code)

    def delete_page_fail_fast(self, request_result: RequestResult):
        self.__return_error(request_result.response.code)

    def __return_error(self, response_code):
        self.send_error(response_code if 300 <= response_code < 500 else 502)

    # Finish page

    def register_renderer(self, renderer: Renderer, priority: int):
        i = bisect(self.renderers, (priority, None))
        self.renderers.insert(i, (priority, renderer))

    def abort(self):
        if self._execute_coroutine is not None:
            self._execute_coroutine.close()

    def is_finished(self):
        return self._finished

    def is_page_handler_finished(self):
        return self._handler_futures is None

    def check_finished(self, callback):
        @wraps(callback)
        def wrapper(*args, **kwargs):
            if self.is_finished():
                self.log.warning('page was already finished, %s ignored', callback)
                return None

            return callback(*args, **kwargs)

        return wrapper

    def schedule_postprocessors(self):
        asyncio.create_task(self._postprocess())

    async def _postprocess(self):
        if self._finished:
            self.log.info('page was already finished, skipping postprocessors')
            return

        postprocessors_completed = await self._run_postprocessors(self._postprocessors)

        if not postprocessors_completed:
            self.log.info('page was already finished, skipping renderer')
            return

        renderer = next((p for _, p in self.renderers if p.can_apply()), None)  # type: Renderer
        if renderer is None:
            await self.finish()
            return

        self.log.debug('using %s renderer', renderer)
        rendered_result = await renderer.render()

        postprocessed_result = await self._run_render_postprocessors(self._render_postprocessors, rendered_result)
        if postprocessed_result is not None:
            await self.finish(postprocessed_result)

    def on_connection_close(self):
        super().on_connection_close()

        self.abort()
        self.cleanup()

    def register_exception_hook(self, exception_hook: 'ExceptionHook') -> None:
        """
        Adds a function to the list of hooks, which are executed when `log_exception` is called.
        `exception_hook` must have the same signature as `log_exception`
        """
        self._exception_hooks.append(exception_hook)

    def log_exception(self, typ: 'ExceptionType', value: 'ExceptionInstance', tb: 'TracebackInstance') -> None:
        super().log_exception(typ, value, tb)

        for exception_hook in self._exception_hooks:
            exception_hook(typ, value, tb)

    def _handle_request_exception(self, e):
        if isinstance(e, AbortPage):
            self.log.info('page was aborted')

        elif isinstance(e, FinishWithPostprocessors):
            if e.wait_handler:
                asyncio.create_task(self._wait_handler_and_schedule_postprocessors())
            else:
                self.schedule_postprocessors()

        elif isinstance(e, FailFastError):
            self._handle_fail_fast_error(e)

        else:
            super()._handle_request_exception(e)

    async def _wait_handler_and_schedule_postprocessors(self):
        await self._wait_handler_futures()
        await self._postprocess()

    def _handle_fail_fast_error(self, e: FailFastError):
        response = e.failed_request.response
        request = e.failed_request.request

        if self.log.isEnabledFor(logging.WARNING):
            _max_uri_length = 24

            request_name = request.get_host() + request.uri[:_max_uri_length]
            if len(request.uri) > _max_uri_length:
                request_name += '...'
            if request.name:
                request_name = f'{request_name} ({request.name})'

            self.log.warning('FailFastError: request %s failed with %s code', request_name, response.code)

        try:
            error_method_name = f'{self.request.method.lower()}_page_fail_fast'
            method = getattr(self, error_method_name, None)
            if callable(method):
                method(e.failed_request)
            else:
                self.__return_error(e.failed_request.response.code)

        except Exception as exc:
            super()._handle_request_exception(exc)

    def send_error(self, status_code: int = 500, **kwargs: 'Any') -> None:
        """`send_error` is adapted to support `write_error` that can call
        `finish` asynchronously.
        """

        if self._headers_written:
            super().send_error(status_code, **kwargs)
            return

        reason = kwargs.get('reason')
        if 'exc_info' in kwargs:
            exception = kwargs['exc_info'][1]
            if isinstance(exception, tornado.web.HTTPError) and exception.reason:
                reason = exception.reason
        else:
            exception = None

        if not isinstance(exception, HTTPErrorWithPostprocessors):
            self.clear()

        self.set_status(status_code, reason=reason)

        try:
            self.write_error(status_code, **kwargs)
        except Exception:
            self.log.exception('Uncaught exception in write_error')
            if not self._finished:
                self.finish()

    def write_error(self, status_code: int = 500, **kwargs: 'Any') -> None:
        """
        `write_error` can call `finish` asynchronously if HTTPErrorWithPostprocessors is raised.
        """

        if 'exc_info' in kwargs:
            exception = kwargs['exc_info'][1]
        else:
            exception = None

        if isinstance(exception, HTTPErrorWithPostprocessors):
            self.schedule_postprocessors()
            return

        self.set_header('Content-Type', media_types.TEXT_HTML)
        super().write_error(status_code, **kwargs)

    def cleanup(self):
        if hasattr(self, 'active_limit'):
            self.active_limit.release()

    def finish(self, chunk=None):
        if self._status_code in (204, 304) or (100 <= self._status_code < 200):
            self._write_buffer = []
            chunk = None

        try:
            return super().finish(chunk)
        finally:
            self.cleanup()

    # Preprocessors and postprocessors

    def add_preprocessor_future(self, future: Future):
        if self._preprocessor_futures is None:
            raise Exception(
                'preprocessors chain is already finished, calling add_preprocessor_future at this time is incorrect'
            )

        self._preprocessor_futures.append(future)
        return future

    async def _run_preprocessors(self, preprocessors):
        for p in preprocessors:
            await p(self)
            if self._finished:
                self.log.info('page was already finished, breaking preprocessors chain')
                return False

        while self._preprocessor_futures:
            futures = self._preprocessor_futures[:]
            self._preprocessor_futures = []
            await asyncio.gather(*futures)

        self._preprocessor_futures = None

        if self._finished:
            self.log.info('page was already finished, breaking preprocessors chain')
            return False

        return True

    async def _run_postprocessors(self, postprocessors):
        for p in postprocessors:
            await p(self)

            if self._finished:
                self.log.warning('page was already finished, breaking postprocessors chain')
                return False

        return True

    async def _run_render_postprocessors(self, postprocessors, rendered_template):
        for p in postprocessors:
            rendered_template = await p(self, rendered_template)

            if self._finished:
                self.log.warning('page was already finished, breaking postprocessors chain')
                return None

        return rendered_template

    def add_render_postprocessor(self, postprocessor: 'RenderPostprocessor') -> None:
        self._render_postprocessors.append(postprocessor)

    def add_postprocessor(self, postprocessor: 'Postprocessor') -> None:
        self._postprocessors.append(postprocessor)

    # HTTP client methods

    def modify_http_client_request(self, balanced_request: 'BalancedHttpRequest'):
        if self.debug_mode.pass_debug:
            balanced_request.headers[DEBUG_HEADER_NAME] = 'true'

            # debug_timestamp is added to avoid caching of debug responses
            balanced_request.uri = make_url(balanced_request.uri, debug_timestamp=int(time.time()))

            for header_name in ('Authorization', DEBUG_AUTH_HEADER_NAME):
                authorization = self.request.headers.get(header_name)
                if authorization is not None:
                    balanced_request.headers[header_name] = authorization

    def get_url(self, host: str, uri: str, *, name: str = None, data=None, headers=None, follow_redirects=True,
                connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                callback=None, waited=True, parse_response=ParseMode.ALWAYS, fail_fast=False):

        client_method = lambda callback: self._http_client.get_url(
            host, uri, name=name, data=data, headers=headers, follow_redirects=follow_redirects,
            connect_timeout=connect_timeout, request_timeout=request_timeout, max_timeout_tries=max_timeout_tries,
            callback=callback, parse_response=parse_response, fail_fast=fail_fast
        )

        return self._execute_http_client_method(host, uri, client_method, waited, callback)

    def head_url(self, host: str, uri: str, *, name: str = None, data=None, headers=None, follow_redirects=True,
                 connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                 callback=None, waited=True, fail_fast=False):

        client_method = lambda callback: self._http_client.head_url(
            host, uri, data=data, name=name, headers=headers, follow_redirects=follow_redirects,
            connect_timeout=connect_timeout, request_timeout=request_timeout, max_timeout_tries=max_timeout_tries,
            callback=callback, fail_fast=fail_fast
        )

        return self._execute_http_client_method(host, uri, client_method, waited, callback)

    def post_url(self, host: str, uri: str, *,
                 name: str = None, data='', headers=None, files=None, content_type=None, follow_redirects=True,
                 connect_timeout=None, request_timeout=None, max_timeout_tries=None, idempotent=False,
                 callback=None, waited=True, parse_response=ParseMode.ALWAYS, fail_fast=False):

        client_method = lambda callback: self._http_client.post_url(
            host, uri, data=data, name=name, headers=headers, files=files, content_type=content_type,
            follow_redirects=follow_redirects, connect_timeout=connect_timeout, request_timeout=request_timeout,
            max_timeout_tries=max_timeout_tries, idempotent=idempotent,
            callback=callback, parse_response=parse_response, fail_fast=fail_fast
        )

        return self._execute_http_client_method(host, uri, client_method, waited, callback)

    def put_url(self, host: str, uri: str, *, name: str = None, data='', headers=None, content_type=None,
                connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                callback=None, waited=True, parse_response=ParseMode.ALWAYS, fail_fast=False):

        client_method = lambda callback: self._http_client.put_url(
            host, uri, name=name, data=data, headers=headers, content_type=content_type,
            connect_timeout=connect_timeout, request_timeout=request_timeout, max_timeout_tries=max_timeout_tries,
            callback=callback, parse_response=parse_response, fail_fast=fail_fast
        )

        return self._execute_http_client_method(host, uri, client_method, waited, callback)

    def delete_url(self, host: str, uri: str, *, name: str = None, data=None, headers=None, content_type=None,
                   connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                   callback=None, waited=True, parse_response=ParseMode.ALWAYS, fail_fast=False):

        client_method = lambda callback: self._http_client.delete_url(
            host, uri, name=name, data=data, headers=headers, content_type=content_type,
            connect_timeout=connect_timeout, request_timeout=request_timeout, max_timeout_tries=max_timeout_tries,
            callback=callback, parse_response=parse_response, fail_fast=fail_fast
        )

        return self._execute_http_client_method(host, uri, client_method, waited, callback)

    def _execute_http_client_method(self, host, uri, client_method, waited, callback):
        if waited and (self.is_finished() or self.is_page_handler_finished()):
            handler_logger.info(
                'attempted to make waited http request to %s %s in finished handler, ignoring', host, uri
            )

            future = Future()
            future.set_exception(AbortPage())
            return future

        if waited and callable(callback):
            callback = self.check_finished(callback)

        def handle_exception(future):
            if future.exception() and not (self.is_finished() or self.is_page_handler_finished()):
                try:
                    raise future.exception()
                except Exception as e:
                    self.abort()
                    self._handle_request_exception(e)

        future = client_method(callback)
        future.add_done_callback(handle_exception)

        if waited:
            self.wait_future(future)

        return future

    # Integrations stubs

    def get_sentry_logger(self) -> 'Optional[SentryLogger]':  # pragma: no cover
        pass

    def get_kafka_producer(self, producer_name: str) -> 'Optional[AIOKafkaProducer]':  # pragma: no cover
        pass

    def get_statsd_client(self) -> 'Optional[StatsdClientWithTags]':  # pragma: no cover
        pass

    def get_consul_client(self) -> 'Optional[Consul]':  # pragma: no cover
        return None


class ErrorHandler(PageHandler, tornado.web.ErrorHandler):
    pass


class RedirectHandler(PageHandler, tornado.web.RedirectHandler):
    pass


class JsonPageHandler(PageHandler):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)

        self._json_renderer = None
        self.json = None

    def prepare(self):
        super().prepare()

        json_renderer = self.application.json_renderer_factory.get_renderer(self)

        self.register_renderer(json_renderer, RendererPriority.JSON)
        self._json_renderer = json_renderer
        self.json = json_renderer.json


class JinjaPageHandler(JsonPageHandler):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)

        self._jinja_renderer = None

    def prepare(self):
        super().prepare()

        jinja_renderer = self.application.jinja_renderer_factory.get_renderer(self)

        self.register_renderer(jinja_renderer, RendererPriority.JINJA)
        self._jinja_renderer = jinja_renderer

    def set_template(self, filename: str):
        return self._jinja_renderer.set_template(filename)

    def get_jinja_context(self) -> dict:
        return self.json.to_dict()


class XmlPageHandler(PageHandler):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)

        self._xml_renderer = None
        self.doc = None

    def prepare(self):
        super().prepare()

        xml_renderer = self.application.xml_renderer_factory.get_renderer(self)

        self.register_renderer(xml_renderer, RendererPriority.XML)
        self._xml_renderer = xml_renderer
        self.doc = xml_renderer.doc

    def xml_from_file(self, filename: str):
        return self._xml_renderer.xml_from_file(filename)


class XsltPageHandler(XmlPageHandler):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)

        self._xslt_renderer = None

    def prepare(self):
        super().prepare()

        xslt_renderer = self.application.xslt_renderer_factory.get_renderer(self)

        self.register_renderer(xslt_renderer, RendererPriority.XSLT)
        self._xslt_renderer = xslt_renderer

    def set_xsl(self, filename: str):
        return self._xslt_renderer.set_xsl(filename)
