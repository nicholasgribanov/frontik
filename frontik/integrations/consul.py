import asyncio
from typing import TYPE_CHECKING

from consul import Check
from consul.aio import Consul

from frontik.integrations import Integration
from frontik.options import options

if TYPE_CHECKING:  # pragma: no cover
    from asyncio import Future
    from typing import Optional

    from frontik.app import FrontikApplication
    from frontik.handler import PageHandler


class ConsulIntegration(Integration):
    def __init__(self):
        self.consul = None

    def initialize_app(self, app: 'FrontikApplication') -> 'Optional[Future]':
        def get_consul_client() -> Consul:
            return self.consul

        app.get_consul_client = get_consul_client

        if options.consul_port:
            self.consul = Consul(port=options.consul_port)

            http_check = Check.http(
                '/status', options.consul_http_check_interval_sec, options.consul_http_check_timeout_sec
            )

            return asyncio.ensure_future(self.consul.agent.service.register(options.app, check=http_check))

        return None

    def initialize_handler(self, handler: 'PageHandler') -> None:
        handler.get_consul_client = handler.application.get_consul_client
