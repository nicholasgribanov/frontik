from frontik.handler import JsonPageHandler


class Page(JsonPageHandler):
    async def get_page(self):
        self.json.put({'get': True})

        self.json.put(self.post_url(self.request.host, self.request.path, waited=False))
        self.json.put(self.put_url(self.request.host, self.request.path, waited=False))
        self.json.put(self.delete_url(self.request.host, self.request.path, waited=False))

    async def post_page(self):
        self.json.put({'post': True})

    async def put_page(self):
        self.json.put({'put': True})

    async def delete_page(self):
        self.json.put({'delete': True})
