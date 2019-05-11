from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(PageHandler):
    async def get_page(self):
        self.application.http_client_factory.register_upstream(
            'retry_on_timeout', {}, [get_server(self, 'broken'), get_server(self, 'normal')]
        )

        delete_response = await self.delete_url(
            'retry_on_timeout', self.request.path, connect_timeout=0.1, request_timeout=0.3, max_timeout_tries=2
        )

        if delete_response.failed:
            raise HTTPError(500)

        self.text = delete_response.data

        check_all_requests_done(self, 'retry_on_timeout')

    async def delete_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
