import asyncio
import logging

from tornado.options import options

statsd_logger = logging.getLogger('frontik.loggers.statsd')

try:
    from aiostatsd.client import StatsdClient
    has_statsd = True
except Exception:
    has_statsd = False


def bootstrap_logger(app):
    if has_statsd and options.statsd_host is not None and options.statsd_port is not None:
        statsd_client = StatsdClientWithTags(
            options.statsd_host, options.statsd_port, packet_size=512, flush_interval=options.statsd_flush_interval_sec,
            default_tags={'app': app.app}
        )
        asyncio.ensure_future(statsd_client.run())
    else:
        statsd_client = StatsdClientStub()

    app.statsd_client = statsd_client

    def logger_initializer(handler):
        handler.statsd_client = statsd_client

    return logger_initializer


def _convert_tag(name, value):
    return '_is_'.join((name.replace('.', '-'), str(value).replace('.', '-')))


def _build_metric(aspect, tags):
    if not tags:
        return aspect

    return '.'.join((
        aspect, '.'.join(_convert_tag(name, value) for name, value in tags.items() if value is not None)
    ))


class StatsdClientStub(object):
    def __init__(self):
        pass

    def count(self, aspect, delta, **kwargs):
        pass

    def time(self, aspect, value, **kwargs):
        pass

    def gauge(self, aspect, value, **kwargs):
        pass


class StatsdClientWithTags(StatsdClient):
    def __init__(self, host, port, packet_size=512, flush_interval=0.5, default_tags=None):
        super().__init__(host, port, packet_size=packet_size, flush_interval=flush_interval)
        self.default_tags = default_tags

    def count(self, aspect, delta, **kwargs):
        self.send_counter(_build_metric(aspect, dict(self.default_tags, **kwargs)), delta)

    def time(self, aspect, value, **kwargs):
        self.send_timer(_build_metric(aspect, dict(self.default_tags, **kwargs)), value)

    def gauge(self, aspect, value, **kwargs):
        self.send_gauge(_build_metric(aspect, dict(self.default_tags, **kwargs)), value)
