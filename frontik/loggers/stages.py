import logging
import time
from collections import namedtuple

from frontik.request_context import RequestContext

stages_logger = logging.getLogger('stages')


class StagesLogger:
    Stage = namedtuple('Stage', ('name', 'start_time', 'end_time'))

    def __init__(self, request, statsd_client):
        self._last_stage_time = self._start_time = request._start_time
        self._stages = []
        self._statsd_client = statsd_client

    def commit_stage(self, stage_name):
        stage_end_time = time.time()
        stage = StagesLogger.Stage(stage_name, self._last_stage_time, stage_end_time)

        self._stages.append(stage)

        if stages_logger.isEnabledFor(logging.DEBUG):
            stages_logger.debug(
                'stage "%s" completed in %.2fms', stage.name, (stage_end_time - self._last_stage_time) * 1000,
                extra={'_stage': stage}
            )

        self._last_stage_time = stage_end_time

    def flush_stages(self, status_code):
        """Writes available stages, total value and status code"""

        stages_delta = [(s.name, (s.end_time - s.start_time) * 1000) for s in self._stages]

        self._statsd_client.stack()

        for stage, delta in stages_delta:
            self._statsd_client.time('handler.stages.{}.time'.format(stage), int(delta))

        self._statsd_client.flush()

        stages_str = ' '.join('{0}={1:.2f}'.format(*s) for s in stages_delta)
        total = sum(s[1] for s in stages_delta)

        stages_logger.info(
            'timings for %(page)s : %(stages)s',
            {
                'page': RequestContext.get('handler_name'),
                'stages': '{0} total={1:.2f} code={2}'.format(stages_str, total, status_code)
            },
        )
