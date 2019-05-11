from frontik import handler, media_types

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(handler.PageHandler):
    async def get_page(self):
        self.application.http_client_factory.register_upstream(
            'no_retry_error', {}, [get_server(self, 'broken'), get_server(self, 'normal')]
        )

        post_result = await self.post_url('no_retry_error', self.request.path)

        if post_result.response.error and post_result.response.code == 500:
            self.text = 'no retry error'
            return

        self.text = post_result.data

        check_all_requests_done(self, 'no_retry_error')

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
