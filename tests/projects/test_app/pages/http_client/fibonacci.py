import asyncio

from frontik import media_types
from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        n = int(self.get_argument('n'))

        self.add_header('Content-Type', media_types.TEXT_PLAIN)

        if n < 2:
            self.text = '1'
            return

        self.acc = 0

        def intermediate_cb(text, response):
            self.acc += int(text)

        await asyncio.gather(
            self.get_url(self.request.host, self.request.path, data={'n': str(n - 1)}, callback=intermediate_cb),
            self.get_url(self.request.host, self.request.path, data={'n': str(n - 2)}, callback=intermediate_cb)
        )

        self.text = str(self.acc)
