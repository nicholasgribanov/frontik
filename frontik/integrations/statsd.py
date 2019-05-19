import asyncio
from asyncio import Future
from typing import TYPE_CHECKING

from aiostatsd.client import StatsdClient

from frontik.integrations import Integration, integrations_logger
from frontik.options import options

if TYPE_CHECKING:  # pragma: no cover
    from asyncio import Future
    from typing import Dict, Optional

    from frontik.app import FrontikApplication
    from frontik.handler import PageHandler


class StatsdIntegration(Integration):
    def __init__(self):
        self.statsd_client = None

    def initialize_app(self, app: 'FrontikApplication') -> 'Optional[Future]':
        if options.statsd_host is not None and options.statsd_port is not None:
            self.statsd_client = StatsdClientWithTags(
                options.statsd_host, options.statsd_port,
                packet_size=options.statsd_packet_size_bytes, flush_interval=options.statsd_flush_interval_sec,
                default_tags={'app': app.app}
            )
            asyncio.create_task(self.statsd_client.run())
        else:
            integrations_logger.info(
                'statsd integration is disabled: statsd_host / statsd_port options are not configured'
            )

        app.get_statsd_client = lambda: self.statsd_client
        return None

    def initialize_handler(self, handler: 'PageHandler') -> None:
        handler.get_statsd_client = lambda: self.statsd_client


def _convert_tag(name: str, value: str) -> str:
    name = name.replace('.', '-')
    value = str(value).replace('.', '-')
    return f'{name}_is_{value}'


def _build_metric(aspect: str, tags: 'Dict[str, str]') -> str:
    if not tags:
        return aspect

    tags_str = '.'.join(_convert_tag(name, value) for name, value in tags.items() if value is not None)

    return f'{aspect}.{tags_str}'


class StatsdClientWithTags(StatsdClient):
    def __init__(self, host, port, packet_size=16 * 1024, flush_interval=1, default_tags=None):
        super().__init__(host, port, packet_size=packet_size, flush_interval=flush_interval)
        self.default_tags = default_tags

    def count(self, aspect, delta, **kwargs):
        self.send_counter(_build_metric(aspect, dict(self.default_tags, **kwargs)), delta)

    def time(self, aspect, value, **kwargs):
        self.send_timer(_build_metric(aspect, dict(self.default_tags, **kwargs)), value)

    def gauge(self, aspect, value, **kwargs):
        self.send_gauge(_build_metric(aspect, dict(self.default_tags, **kwargs)), value)
