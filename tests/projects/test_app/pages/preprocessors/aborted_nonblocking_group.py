import asyncio

from tornado.concurrent import Future

from frontik.handler import FinishWithPostprocessors, PageHandler
from frontik.preprocessors import preprocessor


@preprocessor
async def pp1(handler):
    handler.set_header('content-type', 'text/plain')


@preprocessor
async def pp2(handler):
    future = Future()

    def _cb(*_):
        if handler.get_argument('finish', None):
            handler.set_status(400)
            handler.finish('DONE_IN_PP')
            future.set_result(None)

        elif handler.get_argument('abort', None):
            async def _pp(_):
                # Ensure that page method is scheduled before postprocessors
                await asyncio.sleep(0.1)
                if handler.get_status() == 200:
                    handler.set_status(400)

            handler.add_postprocessor(_pp)
            future.set_exception(FinishWithPostprocessors())

    handler.add_preprocessor_future(future)
    handler.post_url(handler.request.host, handler.request.uri + '&from=pp', callback=_cb)


class Page(PageHandler):
    @pp1
    @pp2
    def get_page(self):
        # Page handler method must not be called
        self.set_status(404)

    @pp1
    def post_page(self):
        pass
