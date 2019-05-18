from frontik import handler, media_types


class Page(handler.PageHandler):
    async def get_page(self):
        result = await self.post_url(self.request.host, self.request.path, data='some data')
        self.text = result.data

    async def post_page(self):
        assert self.request.headers.get('content-length') == '9'
        assert self.request.headers.get('content-type') == media_types.APPLICATION_FORM_URLENCODED

        self.add_header('content-type', media_types.TEXT_PLAIN)
        self.text = 'post_url success'
