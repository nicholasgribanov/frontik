from frontik.handler import JinjaPageHandler


class Page(JinjaPageHandler):
    def get_jinja_context(self):
        if self.get_argument('custom_render', 'false') == 'true':
            return {
                'req1': {'result': 'custom1'},
                'req2': {'result': 'custom2'},
            }

        return super().get_jinja_context()

    async def get_page(self):
        data = {
            'req1': self.post_url(self.request.host, self.request.path, data={'param': 1}),
            'req2': self.post_url(self.request.host, self.request.path, data={'param': 2})
        }

        if self.get_argument('template_error', 'false') == 'true':
            del data['req1']

        self.set_template(self.get_argument('template', 'jinja.html'))
        self.json.put(data)

    async def post_page(self):
        self.json.put({
            'result': self.get_argument('param')
        })
