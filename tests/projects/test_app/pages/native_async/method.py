import asyncio

from frontik.handler import PageHandler


class Page(PageHandler):
    def get_page(self):
        yield self.method()

        asyncio.create_task(self.method())

    async def method(self):
        await asyncio.sleep(0)
        self.json.put({'ok': True})
