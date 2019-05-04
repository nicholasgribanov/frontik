from frontik.handler import JinjaPageHandler


class Page(JinjaPageHandler):
    async def get_page(self):
        self.set_template('jinja_custom_environment.html')
        self.json.put({})
