import asyncio

from frontik.handler import JsonPageHandler


class Page(JsonPageHandler):
    async def get_page(self):
        self.post_url(
            self.request.host, self.request.path,
            callback=self.request_callback, request_timeout=0.5
        )

    def request_callback(self, xml, response):
        self.json.put({'error_received': bool(response.error)})

    async def post_page(self):
        await asyncio.sleep(2)
        self.json.put({'timeout_callback': True})
