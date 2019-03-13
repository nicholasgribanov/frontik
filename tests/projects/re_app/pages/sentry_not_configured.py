import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        assert self.get_sentry_logger() is None
