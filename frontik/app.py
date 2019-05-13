import importlib
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
from frontik.loggers import CUSTOM_JSON_EXTRA, JSON_REQUESTS_LOGGER
from frontik.renderers import jinja_renderer, json_renderer, xml_renderer, xslt_renderer
from frontik.routing import FileMappingRouter, FrontikRouter
from frontik.version import version as frontik_version

if TYPE_CHECKING:  # pragma: no cover
    from typing import Optional

    from aiokafka import AIOKafkaProducer
    from tornado.httputil import HTTPServerRequest

    from frontik.integrations.kafka import AIOKafkaProducer
    from frontik.integrations.sentry import SentryLogger
    from frontik.integrations.statsd import StatsDClient


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

        self.http_client_factory = HttpClientFactory(self, getattr(self.config, 'http_upstreams', {}))

        self.router = FrontikRouter(self)
        self.available_integrations, self.default_init_futures = integrations.load_integrations(self)

        super().__init__([
            (r'/version/?', VersionHandler),
            (r'/status/?', StatusHandler),
            (r'.*', self.router),
        ], **settings.get('tornado_settings', {}))

        self.transforms.insert(0, partial(DebugTransform, self))

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

    def init_async(self):
        return []

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

    # Integrations stubs

    def get_sentry_logger(self, request: 'HTTPServerRequest', function) -> 'Optional[SentryLogger]':  # pragma: no cover
        pass

    def get_kafka_producer(self, producer_name: str) -> 'Optional[AIOKafkaProducer]':  # pragma: no cover
        pass

    def get_statsd_client(self) -> 'Optional[StatsDClient]':  # pragma: no cover
        pass
