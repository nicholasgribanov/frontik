from frontik.handler import JsonPageHandler


class Page(JsonPageHandler):
    async def get_page(self):
        handler_callback_called = False

        def main_callback(json, response):
            self.json.put({
                'fetch_callback_called': True
            })

        def handler_callback():
            nonlocal handler_callback_called
            handler_callback_called = True
            self.json.put({
                'handler_callback_called': True
            })

        def done_callback(future):
            assert future is request_future

            self.json.put({
                'done_callback_called': True
            })

            self.add_callback(self.wait_callback(handler_callback))
            assert not handler_callback_called

        request_future = self.post_url(self.request.host, self.request.path, callback=main_callback)
        request_future.add_done_callback(done_callback)

    async def post_page(self):
        self.json.put({
            'yay': 'yay'
        })
