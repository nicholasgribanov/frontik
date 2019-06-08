import gc
import time
from functools import partial
from typing import TYPE_CHECKING

from tornado.ioloop import PeriodicCallback

from frontik.integrations import Integration, integrations_logger
from frontik.options import options

if TYPE_CHECKING:  # pragma: no cover
    from asyncio import Future
    from typing import Optional

    from frontik.app import FrontikApplication
    from frontik.handler import PageHandler


class GCMetricsCollectorIntegration(Integration):
    def initialize_app(self, app: 'FrontikApplication') -> 'Optional[Future]':
        statsd_client = app.get_statsd_client()
        gc_metrics_send_interval_ms = options.gc_metrics_send_interval_ms

        if statsd_client is None:
            integrations_logger.info('GC metrics collector integration is disabled: statsd client is not configured')
            return

        if gc_metrics_send_interval_ms is None or gc_metrics_send_interval_ms <= 0:
            integrations_logger.info(
                'GC metrics collector integration is disabled: gc_metrics_send_interval_ms option is not configured'
            )
            return

        gc.callbacks.append(gc_metrics_collector)

        PeriodicCallback(partial(send_metrics, app.get_statsd_client()), gc_metrics_send_interval_ms).start()

    def initialize_handler(self, handler: 'PageHandler') -> None:
        pass


class GCStats:
    start = None
    duration = 0
    count = 0


def gc_metrics_collector(phase, info):
    if phase == 'start':
        GCStats.start = time.time()
    elif phase == 'stop' and GCStats.start is not None:
        GCStats.duration += time.time() - GCStats.start
        GCStats.count += 1


def send_metrics(app: 'FrontikApplication') -> None:
    statsd_client = app.get_statsd_client()
    if statsd_client is None:
        return

    if GCStats.count == 0:
        statsd_client.time('gc.duration', 0)
        statsd_client.count('gc.count', 0)
    else:
        statsd_client.time('gc.duration', int(GCStats.duration * 1000))
        statsd_client.count('gc.count', GCStats.count)
        GCStats.duration = GCStats.count = 0
