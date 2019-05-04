import logging
import weakref

from frontik import media_types
from frontik.json_builder import JsonBuilder
from frontik.renderers import Renderer, RendererFactory

json_renderer_logger = logging.getLogger('json_renderer')


class JsonRendererFactory(RendererFactory):
    def __init__(self, application):
        pass

    def get_renderer(self, handler) -> 'JsonRenderer':
        return JsonRenderer(handler, getattr(handler, 'json_encoder', None))


class JsonRenderer(Renderer):
    def __init__(self, handler, json_encoder):
        self.handler = weakref.proxy(handler)
        self.json = JsonBuilder(json_encoder)

    def can_apply(self) -> bool:
        return not self.json.is_empty()

    async def render(self):
        json_renderer_logger.debug('finishing without templating')
        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', media_types.APPLICATION_JSON)

        return self.json.to_string()
