import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sentry_sdk.client import Client
from sentry_sdk.hub import Hub
from sentry_sdk.integrations.tornado import TornadoRequestExtractor
from sentry_sdk.scope import Scope
from sentry_sdk.transport import Transport
from sentry_sdk.utils import Auth, transaction_from_function
from tornado.httpclient import AsyncHTTPClient
from tornado.web import HTTPError

from frontik import media_types
from frontik.integrations import Integration, integrations_logger
from frontik.http_client import FailFastError
from frontik.options import options

if TYPE_CHECKING:  # pragma: no cover
    from asyncio import Future
    from typing import Any, Callable, Dict, Optional, Tuple, Type, Union

    from sentry_sdk.consts import ClientOptions
    from tornado.httputil import HTTPServerRequest

    from frontik.app import FrontikApplication
    from frontik.handler import PageHandler

    ExcInfo = Tuple[
        Optional[Type[BaseException]], Optional[BaseException], Optional[Any]
    ]

sentry_logger = logging.getLogger('sentry_logger')


class SentryIntegration(Integration):
    def __init__(self):
        self.sentry_client = None

    def initialize_app(self, app: 'FrontikApplication') -> 'Optional[Future]':
        if not options.sentry_dsn:
            integrations_logger.info('sentry integration is disabled: sentry_dsn option is not configured')
            return None

        self.sentry_client = Client(
            dsn=options.sentry_dsn,
            max_breadcrumbs=0,
            release=app.application_version(),
            default_integrations=False,
            transport=FrontikTransport,
            before_send=FrontikTransport.before_send,
            attach_stacktrace=True
        )

        self.sentry_client.transport.prepare(app)

        def get_sentry_logger(request, function):
            return SentryLogger(request, function, self.sentry_client)

        app.get_sentry_logger = get_sentry_logger

        return None

    def initialize_handler(self, handler: 'PageHandler') -> None:
        if self.sentry_client is None:
            return

        def get_sentry_logger():
            if not hasattr(handler, 'sentry_logger'):
                handler.sentry_logger = handler.application.get_sentry_logger(
                    handler.request, getattr(handler, f'{handler.request.method.lower()}_page', None)
                )
                if hasattr(handler, 'initialize_sentry_logger'):
                    handler.initialize_sentry_logger(handler.sentry_logger)

            return handler.sentry_logger

        # Defer logger creation after exception actually occurs
        def log_exception_to_sentry(typ, value, tb):
            if isinstance(value, (HTTPError, FailFastError)):
                return

            handler.get_sentry_logger().capture_exception((typ, value, tb))

        handler.get_sentry_logger = get_sentry_logger
        handler.register_exception_hook(log_exception_to_sentry)


class FrontikTransport(Transport):
    def __init__(self, options: 'ClientOptions'):
        super().__init__(options)

        self._disabled_until = None  # type: Optional[datetime]

    def prepare(self, app: 'FrontikApplication'):
        self._auth = self.parsed_dsn.to_auth(app.app)  # type: Auth
        self._http_client = app.http_client_factory.tornado_http_client  # type: AsyncHTTPClient

    def capture_event(self, event: 'Dict[str, Any]') -> None:
        if self._disabled_until is not None:
            if datetime.utcnow() < self._disabled_until:
                return
            self._disabled_until = None

        asyncio.get_event_loop().create_task(self._send_event(event))

    @staticmethod
    def before_send(event: 'Dict[str, Any]', hint: 'Dict[str, Any]') -> 'Optional[Dict[str, Any]]':
        try:
            sample_rate = float(event.get('extra', {}).get('sample_rate', 1.0))
            if sample_rate < 1.0 and random.random() >= sample_rate:
                return None
        except Exception:
            sentry_logger.error('exception %s while sending event to Sentry (before_send)')

        return event

    async def _send_event(self, event: 'Dict[str, Any]'):
        response = await self._http_client.fetch(
            self._auth.store_api_url,
            raise_error=False,
            method='POST', body=json.dumps(event, allow_nan=False),
            headers={
                'x-sentry-auth': str(self._auth.to_header()),
                'content-type': media_types.APPLICATION_JSON,
            }
        )

        if response.code == 429:
            sentry_logger.error('got %s from sentry, enabling backoff', response.code)
            self._disabled_until = datetime.utcnow() + timedelta(seconds=10)
        elif response.error:
            sentry_logger.error('got %s from sentry', response.code)


class SentryLogger:
    def __init__(self, request: 'HTTPServerRequest', function: 'Optional[Callable]', sentry_client: Client):
        self.sentry_client = sentry_client
        self.request = request
        self._user = {}  # type: Dict[str, Any]
        self._extra = {}  # type: Dict[str, Any]

        self._scope = Scope()
        self._scope.add_event_processor(self._event_processor)
        self._scope.transaction = transaction_from_function(function)

    @property
    def user(self):
        return self._user

    @user.setter
    def user(self, user_data):
        self._user = user_data

    @property
    def extra(self):
        return self._extra

    @extra.setter
    def extra(self, extra_data):
        self._extra = extra_data

    def capture_exception(self, error: 'Optional[Union[BaseException, ExcInfo]]' = None) -> 'Optional[str]':
        self._update_scope()

        with Hub(self.sentry_client, self._scope) as hub:
            return hub.capture_exception(error)

    def capture_message(self, message: str, level: 'Optional[str]' = None) -> 'Optional[str]':
        self._update_scope()

        with Hub(self.sentry_client, self._scope) as hub:
            return hub.capture_message(message, level)

    def _update_scope(self):
        self._scope.user = self._user
        for k, v in self._extra.items():
            self._scope.set_extra(k, v)

    def _event_processor(self, event: 'Dict[str, Any]', hint: 'Dict[str, Any]') -> 'Dict[str, Any]':
        extractor = TornadoRequestExtractor(self.request)
        extractor.extract_into_event(event)

        request_info = event['request']
        request_info['url'] = f'{self.request.protocol}://{self.request.host}{self.request.path}'
        request_info['query_string'] = self.request.query
        request_info['method'] = self.request.method
        request_info['env'] = {'REMOTE_ADDR': self.request.remote_ip}
        request_info['headers'] = dict(self.request.headers)

        if event.get('user', {}).get('ip_address') is None:
            event.setdefault('user')['ip_address'] = self.request.remote_ip

        return event
