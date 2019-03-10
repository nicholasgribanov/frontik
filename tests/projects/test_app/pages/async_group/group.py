import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        fail_callback = self.get_argument('fail_callback', 'false') == 'true'
        fail_request = self.get_argument('fail_request', 'false') == 'true'

        def _maybe_failing_callback(text, response):
            if fail_callback:
                raise Exception("I'm dying!")

        result = yield {
            '1': self.post_url(self.request.host, self.request.path + '?data=1'),
            '2': self.post_url(self.request.host, self.request.path + '?data=2',
                               callback=_maybe_failing_callback),
            '3': self.post_url(self.request.host, self.request.path,
                               data={'data': '3' if not fail_request else None}, parse_on_error=False)
        }

        self.json.put(result)

    def post_page(self):
        self.json.put({
            self.get_argument('data'): 'yay'
        })
