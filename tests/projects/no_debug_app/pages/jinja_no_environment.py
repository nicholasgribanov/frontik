from frontik.handler import JinjaPageHandler


class Page(JinjaPageHandler):
    async def get_page(self):
        self.set_template('empty.html')
        self.json.put({'x': 'y'})
