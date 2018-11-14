import logging
import time

from tornado.options import options

from frontik.request_context import context, RequestContext

_logger = logging.getLogger('frontik.handler')
_slow_stage_logger = logging.getLogger('frontik.slow_stage')


class RequestLogger(logging.LoggerAdapter):

    class Stage:
        __slots__ = ('name', 'start_time', 'end_time')

        def __init__(self, name, start_time, end_time):
            self.name = name
            self.start_time = start_time
            self.end_time = end_time

    def __init__(self, request):
        self._last_stage_time = self._start_time = request._start_time

        self.named_stages = {}
        self.page_stages = []

        super().__init__(_logger, {})

    def log_page_stage(self, stage_name):
        stage_end_time = time.time()
        stage = RequestLogger.Stage(stage_name, self._last_stage_time, stage_end_time)

        self.page_stages.append(stage)

        if self.isEnabledFor(logging.DEBUG):
            self.debug(
                'stage "%s" completed in %.2fms', stage.name, (stage_end_time - self._last_stage_time) * 1000,
                extra={'_stage': stage}
            )

        self._last_stage_time = stage_end_time

    def start_stage(self, stage_name):
        stage_start_time = time.time()
        self.named_stages[stage_name] = RequestLogger.Stage(stage_name, stage_start_time, None)

    def end_stage(self, stage_name):
        if stage_name not in self.named_stages:
            self.warning('unable to end stage %s — stage was not started', stage_name)
            return

        stage_end_time = time.time()
        stage = self.named_stages[stage_name]
        stage.end_time = stage_end_time

        if options.slow_callback_threshold_ms is not None:
            stage_delta = (stage_end_time - stage.start_time) * 1000
            if stage_delta >= options.slow_callback_threshold_ms:
                _slow_stage_logger.warning('slow stage %s took %s ms', stage_name, stage_delta)

    def flush_page_stages(self, status_code):
        """Writes available stages, total value and status code"""

        stages_delta = [(s.name, (s.end_time - s.start_time) * 1000) for s in self.page_stages]
        stages_str = ' '.join('{0}={1:.2f}'.format(*s) for s in stages_delta)
        total = sum(s[1] for s in stages_delta)

        self.info(
            'timings for %(page)s : %(stages)s',
            {
                'page': RequestContext.get('handler_name') or context.get().handler_name,
                'stages': '{0} total={1:.2f} code={2}'.format(stages_str, total, status_code)
            },
        )

    def process(self, msg, kwargs):
        if 'extra' in kwargs:
            kwargs['extra'].update(self.extra)
        else:
            kwargs['extra'] = self.extra

        return msg, kwargs
