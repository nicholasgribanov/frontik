import copy
import logging
import os
import weakref
from functools import lru_cache

from tornado.options import options

from frontik import media_types
from frontik.doc import Doc
from frontik.renderers import Renderer, RendererFactory
from frontik.util import get_abs_path
from frontik.xml_util import xml_from_file

xml_renderer_logger = logging.getLogger('xml_renderer')


class XmlRendererFactory(RendererFactory):
    def __init__(self, application):
        xml_root = get_abs_path(application.app_root, options.xml_root)

        @lru_cache(options.xml_cache_limit)
        def xml_from_file_cached(file):
            return xml_from_file(os.path.normpath(os.path.join(xml_root, file)))

        self.xml_from_file_cached = xml_from_file_cached

    def get_renderer(self, handler) -> 'XmlRenderer':
        return XmlRenderer(handler, self.xml_from_file_cached)


class XmlRenderer(Renderer):
    def __init__(self, handler, xml_from_file_cached):
        self.handler = weakref.proxy(handler)
        self.xml_from_file_cached = xml_from_file_cached
        self.doc = Doc()

    def can_apply(self) -> bool:
        return True

    def xml_from_file(self, filename: str):
        return copy.deepcopy(self.xml_from_file_cached(filename))

    async def render(self):
        xml_renderer_logger.debug('finishing without XSLT')
        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', media_types.APPLICATION_XML)

        return self.doc.to_string()
