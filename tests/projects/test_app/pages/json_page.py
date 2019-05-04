from frontik import media_types
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
        invalid_json = self.get_argument('invalid', 'false')

        data = {
            'req1': self.post_url(self.request.host, self.request.path, data={'param': 1}),
            'req2': self.post_url(self.request.host, self.request.path, data={'param': 2, 'invalid': invalid_json})
        }

        if self.get_argument('template_error', 'false') == 'true':
            del data['req1']

        self.set_template(self.get_argument('template', 'jinja.html'))
        self.json.put(data)

    async def post_page(self):
        invalid_json = self.get_argument('invalid', 'false') == 'true'

        if not invalid_json:
            self.json.put({
                'result': self.get_argument('param')
            })
        else:
            self.set_header('Content-Type', media_types.APPLICATION_JSON)
            self.text = '{"result": FAIL}'
