from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        self.set_header('X-Foo', 'Bar')
        self.text = 'response body must be empty for HEAD requests'
