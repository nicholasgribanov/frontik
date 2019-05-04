from frontik.handler import JsonPageHandler


class Page(JsonPageHandler):
    async def get_page(self):
        self.json.put({
            'тест': self.get_argument('param')
        })
