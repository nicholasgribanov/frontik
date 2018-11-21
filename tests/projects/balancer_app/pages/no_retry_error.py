import frontik.handler
from frontik.futures import AsyncGroup

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.application.http_client_factory.register_upstream('no_retry_error', {},
                                                               [get_server(self, 'broken'), get_server(self, 'normal')])

        def check_requests_cb():
            check_all_requests_done(self, 'no_retry_error')

        async_group = AsyncGroup(check_requests_cb)

        def callback_post(text, response):
            if response.error and response.code == 500:
                self.text = 'no retry error'
                return

            self.text = text

        self.post_url('no_retry_error', self.request.path, callback=async_group.add(callback_post))

    def post_page(self):
        self.add_header('Content-Type', 'text/plain')
        self.text = 'result'
