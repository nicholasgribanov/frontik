import asyncio

from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_occupied


class Page(PageHandler):
    async def get_page(self):
        self.application.http_client_factory.register_upstream(
            'retry_connect', {}, [get_server(self, 'free'), get_server(self, 'normal')]
        )
        self.text = ''

        def callback_post(text, response):
            if response.error or text is None:
                raise HTTPError(500)

            self.text = self.text + text

        futures = [
            self.post_url('retry_connect', self.request.path, callback=callback_post),
            self.post_url('retry_connect', self.request.path, callback=callback_post),
            self.post_url('retry_connect', self.request.path, callback=callback_post)
        ]

        check_all_servers_occupied(self, 'retry_connect')

        await asyncio.gather(*futures)

        check_all_requests_done(self, 'retry_connect')

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
