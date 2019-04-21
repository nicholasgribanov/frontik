from tornado import gen

from frontik.handler import PageHandler
from frontik.http_client import ParseMode


class Page(PageHandler):
    async def get_page(self):
        fail_callback = self.get_argument('fail_callback', 'false') == 'true'
        fail_request = self.get_argument('fail_request', 'false') == 'true'

        def _maybe_failing_callback(text, response):
            if fail_callback:
                raise Exception("I'm dying!")

        result = await gen.multi({
            '1': self.post_url(self.request.host, self.request.path + '?data=1'),
            '2': self.post_url(self.request.host, self.request.path + '?data=2', callback=_maybe_failing_callback),
            '3': self.post_url(
                self.request.host, self.request.path,
                data={'data': '3' if not fail_request else None},
                parse_response=ParseMode.ON_SUCCESS
            )
        })

        self.json.put(result)

    async def post_page(self):
        self.json.put({
            self.get_argument('data'): 'yay'
        })
