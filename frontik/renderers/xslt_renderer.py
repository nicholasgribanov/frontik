import contextvars
import copy
import logging
import os
import time
import weakref
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from lxml import etree
from tornado.ioloop import IOLoop
from tornado.options import options

import frontik.doc
import frontik.util
from frontik import media_types
from frontik.renderers import Renderer, RendererFactory
from frontik.util import get_abs_path
from frontik.xml_util import xsl_from_file

xslt_renderer_logger = logging.getLogger('xslt_renderer')


class XsltRendererFactory(RendererFactory):
    def __init__(self, application):
        xsl_root = get_abs_path(application.app_root, options.xsl_root)

        @lru_cache(options.xsl_cache_limit)
        def xsl_from_file_cached(file):
            return xsl_from_file(os.path.normpath(os.path.join(xsl_root, file)))

        self.xsl_from_file_cached = xsl_from_file_cached
        self.executor = ThreadPoolExecutor(options.xsl_executor_pool_size)

    def get_renderer(self, handler) -> 'XsltRenderer':
        return XsltRenderer(handler, self.xsl_from_file_cached, self.executor)


class XsltRenderer(Renderer):
    def __init__(self, handler, xsl_from_file_cached, executor):
        self.handler = weakref.proxy(handler)
        self.executor = executor
        self.xsl_from_file_cached = xsl_from_file_cached

        self.transform = None
        self.transform_filename = None

    def can_apply(self):
        if any(frontik.util.get_cookie_or_url_param_value(self.handler, p) is not None for p in ('noxsl', 'notpl')):
            self.handler.require_debug_access()  # TODO: test noxsl notpl with not xslt handler
            xslt_renderer_logger.debug('ignoring XSLT because noxsl/notpl parameter is passed')
            return False

        return self.transform_filename is not None

    def set_xsl(self, filename):
        self.transform_filename = filename

    async def render(self):
        try:
            self.transform = self.xsl_from_file_cached(self.transform_filename)
        except etree.XMLSyntaxError:
            xslt_renderer_logger.error('failed parsing XSL file %s (XML syntax)', self.transform_filename)
            raise
        except etree.XSLTParseError:
            xslt_renderer_logger.error('failed parsing XSL file %s (XSL parse error)', self.transform_filename)
            raise
        except Exception:
            xslt_renderer_logger.error('failed loading XSL file %s', self.transform_filename)
            raise

        xslt_renderer_logger.debug('finishing with XSLT')

        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', media_types.TEXT_HTML)

        def job():
            start_time = time.time()
            result = self.transform(
                copy.deepcopy(self.handler.doc.to_etree_element()),
                profile_run=self.handler.debug_mode.profile_xslt
            )
            return start_time, str(result), result.xslt_profile

        def get_xsl_log():
            xsl_line = 'XSLT {0.level_name} in file "{0.filename}", line {0.line}, column {0.column}\n\t{0.message}'
            return '\n'.join(map(xsl_line.format, self.transform.error_log))

        try:
            ctx = contextvars.copy_context()
            xslt_result = await IOLoop.current().run_in_executor(self.executor, lambda: ctx.run(job))
            if self.handler.is_finished():
                return None

            start_time, xml_result, xslt_profile = xslt_result

            xslt_renderer_logger.info(
                'applied XSL %s in %.2fms', self.transform_filename, (time.time() - start_time) * 1000
            )

            if xslt_profile is not None:
                xslt_renderer_logger.debug('XSLT profiling results', extra={'_xslt_profile': xslt_profile.getroot()})

            if len(self.transform.error_log):
                xslt_renderer_logger.warning(get_xsl_log())

            return xml_result

        except Exception as e:
            xslt_renderer_logger.error('failed XSLT %s', self.transform_filename)
            xslt_renderer_logger.error(get_xsl_log())
            raise e
