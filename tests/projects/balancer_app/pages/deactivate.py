import asyncio

from frontik.handler import PageHandler

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_occupied


class Page(PageHandler):
    async def get_page(self):
        server = get_server(self, 'free')
        self.application.http_client_factory.register_upstream(
            'deactivate', {'max_fails': 1, 'fail_timeout_sec': 0.1}, [server]
        )

        self.text = ''

        post_future = self.post_url('deactivate', self.request.path)
        check_all_servers_occupied(self, 'deactivate')

        post_result = await post_future

        if post_result.response.error and post_result.response.code == 502 and not server.is_active:
            self.text = 'deactivated'

        await asyncio.sleep(0.2)

        if server.is_active:
            self.text += ' activated'

        check_all_requests_done(self, 'deactivate')
