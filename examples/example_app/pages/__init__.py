from frontik.handler import JsonPageHandler


class Page(JsonPageHandler):
    async def get_page(self):
        self.json.put({
            'text': 'Hello, world!'
        })
