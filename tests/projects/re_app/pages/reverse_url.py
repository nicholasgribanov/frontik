from frontik.handler import JsonPageHandler


class Page(JsonPageHandler):
    async def get_page(self):
        if self.get_argument('fail_args', 'false') != 'false':
            self.text = self.reverse_url('two_ids', 1)

        if self.get_argument('fail_missing', 'false') != 'false':
            self.text = self.reverse_url('missing', 1)

        self.text = self.reverse_url('two_ids', 1, 2)
