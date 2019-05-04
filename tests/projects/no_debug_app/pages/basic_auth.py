from frontik.handler import JsonPageHandler


class Page(JsonPageHandler):
    async def get_page(self):
        self.require_debug_access('user', 'god')
        self.json.put({'authenticated': True})
