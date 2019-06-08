import importlib
import logging
import sys
import time
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING

import pycurl
import tornado
from lxml import etree
from tornado.options import options
from tornado.web import Application, RequestHandler

from frontik import integrations, request_context
from frontik.debug import DebugTransform
from frontik.handler import ErrorHandler
from frontik.http_client import HttpClientFactory
from frontik.loggers import bootstrap_logger, CUSTOM_JSON_EXTRA, JSON_REQUESTS_LOGGER
from frontik.renderers import jinja_renderer, json_renderer, xml_renderer, xslt_renderer
from frontik.routing import FileMappingRouter, FrontikRouter
from frontik.version import version as frontik_version

if TYPE_CHECKING:  # pragma: no cover
    from typing import Optional

    from aiokafka import AIOKafkaProducer
    from consul.aio import Consul
    from tornado.httputil import HTTPServerRequest

    from frontik.integrations.sentry import SentryLogger
    from frontik.integrations.statsd import StatsdClientWithTags


class VersionHandler(RequestHandler):
    def get(self):
        self.finish(self.application.get_versions())


class StatusHandler(RequestHandler):
    def get(self):
        self.finish(self.application.get_current_status())


class FrontikApplication(Application):
    request_id = 0

    class DefaultConfig:
        pass

    def __init__(self, **settings):
        self.start_time = time.time()
        self.config = self.application_config()
        self.app = settings.get('app')
        self.app_root = settings.get('app_root')

        self.xml_renderer_factory = xml_renderer.XmlRendererFactory(self)
        self.xslt_renderer_factory = xslt_renderer.XsltRendererFactory(self)
        self.json_renderer_factory = json_renderer.JsonRendererFactory(self)
        self.jinja_renderer_factory = jinja_renderer.JinjaRendererFactory(self)

        self.http_client_factory = HttpClientFactory(getattr(self.config, 'http_upstreams', {}))

        self.router = FrontikRouter(self)
        self.slow_tasks_logger = bootstrap_logger('slow_tasks', logging.WARNING, use_json_formatter=False)
        self.integrations = []

        super().__init__([
            (r'/version/?', VersionHandler),
            (r'/status/?', StatusHandler),
            (r'.*', self.router),
        ], **settings.get('tornado_settings', {}))

        self.transforms.insert(0, partial(DebugTransform, self))

    async def init_async(self):
        self.integrations = await integrations.load_integrations(self)

    def find_handler(self, request, **kwargs):
        request_id = request.headers.get('x-request-id')
        if request_id is None:
            request_id = FrontikApplication.next_request_id()

        def wrapped_in_context(func):
            def wrapper(*args, **kwargs):
                token = request_context.initialize(request, request_id)

                try:
                    return func(*args, **kwargs)
                finally:
                    request_context.reset(token)

            return wrapper

        delegate = wrapped_in_context(super().find_handler)(request, **kwargs)
        delegate.headers_received = wrapped_in_context(delegate.headers_received)
        delegate.data_received = wrapped_in_context(delegate.data_received)
        delegate.finish = wrapped_in_context(delegate.finish)
        delegate.on_connection_close = wrapped_in_context(delegate.on_connection_close)

        return delegate

    def reverse_url(self, name, *args, **kwargs):
        return self.router.reverse_url(name, *args, **kwargs)

    def application_urls(self):
        return [
            ('', FileMappingRouter(importlib.import_module(f'{self.app}.pages')))
        ]

    def application_404_handler(self, request):
        return ErrorHandler, {'status_code': 404}

    def application_config(self):
        return FrontikApplication.DefaultConfig()

    def application_version(self):
        return 'unknown'

    @staticmethod
    def next_request_id():
        FrontikApplication.request_id += 1
        return str(FrontikApplication.request_id)

    def get_versions(self):
        return {
            'frontik': frontik_version,
            'tornado': tornado.version,
            'lxml': '.'.join(str(x) for x in etree.LXML_VERSION),
            'libxml': '.'.join(str(x) for x in etree.LIBXML_VERSION),
            'libxslt': '.'.join(str(x) for x in etree.LIBXSLT_VERSION),
            'pycurl': pycurl.version,
            'python': sys.version.replace('\n', ''),
            options.app: self.application_version()
        }

    def get_current_status(self):
        return {
            'started_at': str(datetime.fromtimestamp(self.start_time)),
            'datacenter': options.datacenter,
        }

    def log_request(self, handler):
        if not options.log_json:
            super().log_request(handler)
            return

        request_time = int(1000.0 * handler.request.request_time())
        extra = {
            'ip': handler.request.remote_ip,
            'rid': request_context.get_request_id(),
            'status': handler.get_status(),
            'time': request_time,
            'method': handler.request.method,
            'uri': handler.request.uri,
        }

        handler_name = request_context.get_handler_name()
        if handler_name:
            extra['controller'] = handler_name

        JSON_REQUESTS_LOGGER.info('', extra={CUSTOM_JSON_EXTRA: extra})

    def handle_long_asyncio_task(self, handle, duration_sec):
        duration_ms = duration_sec * 1000
        self.slow_tasks_logger.warning('%s took %.2f ms', handle, duration_ms)

        if options.asyncio_task_critical_threshold_sec and duration_sec >= options.asyncio_task_critical_threshold_sec:
            request = request_context.get_request() or HTTPServerRequest('GET', '/asyncio_long_task_stub')
            sentry_logger = self.get_sentry_logger(request, None)
            sentry_logger.update_user_info(ip='127.0.0.1')

            if sentry_logger:
                self.slow_tasks_logger.warning('no sentry logger available')
                sentry_logger.capture_message(f'{handle} took {duration_ms:.2f} ms')

    # Integrations stubs

    def get_sentry_logger(self, request: 'HTTPServerRequest', function) -> 'Optional[SentryLogger]':  # pragma: no cover
        pass

    def get_kafka_producer(self, producer_name: str) -> 'Optional[AIOKafkaProducer]':  # pragma: no cover
        pass

    def get_statsd_client(self) -> 'Optional[StatsdClientWithTags]':  # pragma: no cover
        pass

    def get_consul_client(self) -> 'Optional[Consul]':  # pragma: no cover
        pass
