import asyncio
import logging
import time
import weakref

import jinja2
from jinja2.utils import concat
from tornado.escape import to_unicode
from tornado.options import options

from frontik import media_types
from frontik.renderers import Renderer, RendererFactory
from frontik.util import get_abs_path, get_cookie_or_url_param_value

jinja_renderer_logger = logging.getLogger('jinja_renderer')


class JinjaRendererFactory(RendererFactory):
    def __init__(self, application):
        if hasattr(application, 'get_jinja_environment'):
            self.environment = application.get_jinja_environment()
        elif options.jinja_template_root is not None:
            self.environment = jinja2.Environment(
                auto_reload=options.debug,
                cache_size=options.jinja_template_cache_limit,
                loader=jinja2.FileSystemLoader(get_abs_path(application.app_root, options.jinja_template_root)),
            )
        else:
            self.environment = None

    def get_renderer(self, handler) -> 'JinjaRenderer':
        return JinjaRenderer(handler, self.environment)


class JinjaRenderer(Renderer):
    def __init__(self, handler, environment):
        self.handler = weakref.proxy(handler)
        self.template_filename = None
        self.environment = environment

    def can_apply(self):
        if get_cookie_or_url_param_value(self.handler, 'notpl') is not None:
            self.handler.require_debug_access()
            jinja_renderer_logger.debug('ignoring templating because notpl parameter is passed')
            return False

        return self.template_filename is not None

    def set_template(self, filename):
        self.template_filename = filename

    async def render(self):
        if not self.environment:
            raise Exception('Cannot apply template, no Jinja2 environment configured')

        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', media_types.TEXT_HTML)

        try:
            render_result = await self._render_template_stream_on_ioloop(options.jinja_streaming_render_timeout_ms)
            if self.handler.is_finished():
                return None

            start_time, result = render_result

            jinja_renderer_logger.info(
                'applied template %s in %.2fms', self.template_filename, (time.time() - start_time) * 1000
            )

            return result

        except Exception as e:
            jinja_renderer_logger.error('failed applying template %s', self.template_filename)

            if isinstance(e, jinja2.TemplateSyntaxError):
                jinja_renderer_logger.error(
                    '%s in file "%s", line %d\n\t%s',
                    e.__class__.__name__, to_unicode(e.filename), e.lineno, to_unicode(e.message)
                )
            elif isinstance(e, jinja2.TemplateError):
                jinja_renderer_logger.error('%s error\n\t%s', e.__class__.__name__, to_unicode(e.message))

            raise e

    async def _render_template_stream_on_ioloop(self, batch_render_timeout_ms):
        template_render_start_time = time.time()
        template = self.environment.get_template(self.template_filename)

        template_stream = template.generate(self.handler.get_jinja_context())
        template_parts = []

        part_index = 1
        while True:
            part_render_start_time = time.time()
            if batch_render_timeout_ms is not None:
                part_render_timeout_time = part_render_start_time + batch_render_timeout_ms / 1000.0
            else:
                part_render_timeout_time = None

            whole_template_render_finished = False
            statements_processed = 0

            while True:
                next_statement_render_result = next(template_stream, None)

                if next_statement_render_result is None:
                    whole_template_render_finished = True
                    break

                statements_processed += 1
                template_parts.append(next_statement_render_result)

                if part_render_timeout_time is not None and time.time() > part_render_timeout_time:
                    break

            taken_time_ms = (time.time() - part_render_start_time) * 1000
            jinja_renderer_logger.info(
                'render template part %s with %s statements in %.2fms', part_index, statements_processed, taken_time_ms
            )

            part_index += 1

            if whole_template_render_finished:
                return template_render_start_time, concat(template_parts)

            await asyncio.sleep(0)
