from tornado.ioloop import IOLoop

from frontik.handler import PageHandler


class Page(PageHandler):
    result = 'Callback not called'

    async def get_page(self):
        # Callback must never be called
        def callback():
            Page.result = 'Callback called'

        IOLoop.current().add_callback(self.check_finished(callback))
        self.finish(Page.result)
