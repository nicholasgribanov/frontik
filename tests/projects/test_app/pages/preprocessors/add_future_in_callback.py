import time
from asyncio import Future

from frontik.handler import JsonPageHandler
from frontik.preprocessors import preprocessor


@preprocessor
async def pp1(handler):
    future = Future()

    def _cb2():
        if not handler.text:
            handler.text = 'ok'

        future.set_result(None)

    def _cb1(_, __):
        handler.add_preprocessor_future(future)
        handler.add_timeout(time.time() + 0.2, _cb2)

    handler.add_preprocessor_future(
        handler.post_url(handler.request.host, handler.request.uri, callback=_cb1)
    )


class Page(JsonPageHandler):
    @pp1
    async def get_page(self):
        if not self.text:
            self.text = 'not ok'

    async def post_page(self):
        pass
