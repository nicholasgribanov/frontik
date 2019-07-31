from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        self.json.put({'ok': True})
