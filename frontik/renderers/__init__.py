import logging
import weakref

from frontik import media_types

generic_renderer_logger = logging.getLogger('generic_renderer')


class RendererFactory:
    def get_renderer(self, handler) -> 'Renderer':
        raise NotImplementedError()  # pragma: no cover


class Renderer:
    def can_apply(self) -> bool:
        raise NotImplementedError()  # pragma: no cover

    async def render(self):
        raise NotImplementedError()  # pragma: no cover

    def __repr__(self):
        return '{}.{}'.format(__package__, self.__class__.__name__)


class GenericRenderer(Renderer):
    def __init__(self, handler):
        self.handler = weakref.proxy(handler)

    def can_apply(self) -> bool:
        return self.handler.text is not None

    async def render(self):
        generic_renderer_logger.debug('finishing plaintext')

        if self.handler._headers.get('Content-Type') is None:
            self.handler.set_header('Content-Type', media_types.TEXT_HTML)

        return self.handler.text
