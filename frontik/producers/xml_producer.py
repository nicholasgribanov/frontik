import copy
import os
import time
import weakref
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from lxml import etree
from tornado import gen
from tornado.options import options

import frontik.doc
import frontik.util
from frontik.producers import ProducerFactory
from frontik.util import get_abs_path
from frontik.xml_util import xml_from_file, xsl_from_file


class XMLProducerFactory(ProducerFactory):
    def __init__(self, application):
        xml_root = get_abs_path(application.app_root, options.xml_root)
        xsl_root = get_abs_path(application.app_root, options.xsl_root)

        @lru_cache(options.xml_cache_limit)
        def xml_from_file_cached(file):
            return xml_from_file(os.path.normpath(os.path.join(xml_root, file)))

        @lru_cache(options.xsl_cache_limit)
        def xsl_from_file_cached(file):
            return xsl_from_file(os.path.normpath(os.path.join(xsl_root, file)))

        self.xml_from_file_cached = xml_from_file_cached
        self.xsl_from_file_cached = xsl_from_file_cached

        self.executor = ThreadPoolExecutor(options.xsl_executor_pool_size)

    def get_producer(self, handler):
        return XmlProducer(handler, self.xml_from_file_cached, self.xsl_from_file_cached, self.executor)


class XmlProducer:
    def __init__(self, handler, xml_from_file_cached, xsl_from_file_cached, executor):
        self.handler = weakref.proxy(handler)
        self.log = weakref.proxy(self.handler.log)
        self.executor = executor

        self.xml_from_file_cached = xml_from_file_cached
        self.xsl_from_file_cached = xsl_from_file_cached

        self.doc = frontik.doc.Doc()
        self.transform = None
        self.transform_filename = None

    def __call__(self):
        if any(frontik.util.get_cookie_or_url_param_value(self.handler, p) is not None for p in ('noxsl', 'notpl')):
            self.handler.require_debug_access()
            self.log.debug('ignoring XSLT because noxsl/notpl parameter is passed')
            return self._finish_with_xml()

        if not self.transform_filename:
            return self._finish_with_xml()

        try:
            self.log.start_stage('xsl_from_file_cached')
            self.transform = self.xsl_from_file_cached(self.transform_filename)
            self.log.end_stage('xsl_from_file_cached')
        except etree.XMLSyntaxError:
            self.log.error('failed parsing XSL file %s (XML syntax)', self.transform_filename)
            raise
        except etree.XSLTParseError:
            self.log.error('failed parsing XSL file %s (XSL parse error)', self.transform_filename)
            raise
        except Exception:
            self.log.error('failed loading XSL file %s', self.transform_filename)
            raise

        return self._finish_with_xslt()

    def set_xsl(self, filename):
        self.transform_filename = filename

    @gen.coroutine
    def _finish_with_xslt(self):
        self.log.debug('finishing with XSLT')

        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', 'text/html; charset=utf-8')

        def job():
            start_time = time.time()
            result = self.transform(copy.deepcopy(self.doc.to_etree_element()),
                                    profile_run=self.handler.debug_mode.profile_xslt)
            return start_time, str(result), result.xslt_profile

        def get_xsl_log():
            xsl_line = 'XSLT {0.level_name} in file "{0.filename}", line {0.line}, column {0.column}\n\t{0.message}'
            return '\n'.join(map(xsl_line.format, self.transform.error_log))

        try:
            xslt_result = yield self.executor.submit(job)
            if self.handler.is_finished():
                return None

            start_time, xml_result, xslt_profile = xslt_result

            self.log.info('applied XSL %s in %.2fms', self.transform_filename, (time.time() - start_time) * 1000)

            if xslt_profile is not None:
                self.log.debug('XSLT profiling results', extra={'_xslt_profile': xslt_profile.getroot()})

            if len(self.transform.error_log):
                self.log.warning(get_xsl_log())

            self.log.log_page_stage('xsl')
            return xml_result

        except Exception as e:
            self.log.error('failed XSLT %s', self.transform_filename)
            self.log.error(get_xsl_log())
            raise e

    @gen.coroutine
    def _finish_with_xml(self):
        self.log.debug('finishing without XSLT')
        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', 'application/xml; charset=utf-8')

        return self.doc.to_string()

    def xml_from_file(self, filename):
        self.log.start_stage('xml_from_file_cached')
        xml = copy.deepcopy(self.xml_from_file_cached(filename))
        self.log.end_stage('xml_from_file_cached')
        return xml

    def __repr__(self):
        return '{}.{}'.format(__package__, self.__class__.__name__)
