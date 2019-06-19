import logging
from typing import TYPE_CHECKING

from tornado.options import options
from tornado.web import HTTPError

if TYPE_CHECKING:  # pragma: no cover
    from typing import Optional

    from frontik.integrations.statsd import StatsdClientWithTags

handlers_count_logger = logging.getLogger('handlers_count')


class ActiveHandlersLimit:
    count = 0

    def __init__(self, statsd_client: 'Optional[StatsdClientWithTags]'):
        self._acquired = False
        self._statsd_client = statsd_client

        if ActiveHandlersLimit.count > options.max_active_handlers:
            handlers_count_logger.warning(
                'dropping request: too many active handlers (%s)', ActiveHandlersLimit.count
            )

            raise HTTPError(503)

        self.acquire()

    def acquire(self):
        if not self._acquired:
            ActiveHandlersLimit.count += 1
            self._acquired = True
            if self._statsd_client is not None:
                self._statsd_client.gauge('handler.active_count', ActiveHandlersLimit.count)

    def release(self):
        if self._acquired:
            ActiveHandlersLimit.count -= 1
            self._acquired = False
            if self._statsd_client is not None:
                self._statsd_client.gauge('handler.active_count', ActiveHandlersLimit.count)
