import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        if self.get_sentry_logger() is None:
            self.text = 'sentry logger is None'
