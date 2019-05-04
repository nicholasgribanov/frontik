from frontik.handler import JinjaPageHandler


class Page(JinjaPageHandler):
    async def get_page(self):
        self.set_template('main.html')  # This template is located in the `templates` folder
        self.json.put(
            self.get_url(self.request.host, '/example')
        )
