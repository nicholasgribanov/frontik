from frontik import media_types
from frontik.handler import JsonPageHandler


class Page(JsonPageHandler):
    async def get_page(self):
        invalid_json = self.get_argument('invalid', 'false')

        self.json.put({
            'req1': self.post_url(self.request.host, self.request.path, data={'invalid': invalid_json}),
            'req2': self.post_url(self.request.host, self.request.path)
        })

        self.set_header('content-type', 'text/json')

    async def post_page(self):
        invalid_json = self.get_argument('invalid', 'false') == 'true'

        if invalid_json:
            self.set_header('content-type', media_types.APPLICATION_JSON)
            self.text = '{"result": FAIL}'
        else:
            self.json.put({
                'result': 'OK'
            })
