import asyncio

from tornado.web import HTTPError

from frontik.handler import JinjaPageHandler


class ContentPostprocessor:
    async def postprocessor(self, handler, tpl):
        await asyncio.sleep(0)
        return tpl.replace('%%content%%', 'CONTENT')


class Page(JinjaPageHandler):
    async def get_page(self):
        if self.get_argument('raise_error', None) is not None:
            self.add_postprocessor(self._error_in_postprocessor)

        if self.get_argument('finish', None) is not None:
            self.add_postprocessor(self._finish_in_postprocessor)

        if self.get_argument('template_finish', None) is not None:
            self.add_postprocessor(self._finish_in_template_postprocessor)

        if self.get_argument('header', None) is not None:
            self.add_render_postprocessor(Page._header_postprocessor)

        if self.get_argument('content', None) is not None:
            content_postprocessor = ContentPostprocessor()
            self.add_render_postprocessor(content_postprocessor.postprocessor)

        self.set_template('postprocess.html')
        self.json.put({'content': '%%content%%'})

    @staticmethod
    async def _error_in_postprocessor(handler):
        raise HTTPError(400)

    @staticmethod
    async def _finish_in_postprocessor(handler):
        handler.finish('FINISH_IN_PP')

    @staticmethod
    async def _finish_in_template_postprocessor(handler):
        handler.finish('FINISH_IN_TEMPLATE_PP')

    async def _header_postprocessor(self, tpl):
        return tpl.replace('%%header%%', 'HEADER')
