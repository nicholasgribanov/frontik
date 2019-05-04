from frontik.handler import HTTPErrorWithPostprocessors, JsonPageHandler


class Page(JsonPageHandler):
    async def get_page(self):
        self.json.put({'reason': 'bad argument'})
        raise HTTPErrorWithPostprocessors(400)
