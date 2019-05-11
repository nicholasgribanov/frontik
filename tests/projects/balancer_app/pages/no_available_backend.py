from frontik import handler, media_types

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(handler.PageHandler):
    async def get_page(self):
        server = get_server(self, 'normal')
        self.application.http_client_factory.register_upstream('no_available_backend', {}, [server])
        server.is_active = False

        post_future = self.post_url('no_available_backend', self.request.path)
        check_all_requests_done(self, 'no_available_backend')

        post_result = await post_future

        if post_result.response.error and post_result.response.code == 502:
            self.text = 'no backend available'
            return

        self.text = post_result.data

        check_all_requests_done(self, 'no_available_backend')

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
