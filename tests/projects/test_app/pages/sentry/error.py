import asyncio

from tornado.web import HTTPError

from frontik.handler import PageHandler
from frontik.integrations.sentry import SentryLogger


class Page(PageHandler):
    async def get_page(self):
        action = self.get_argument('action')

        if action == 'exception':
            raise Exception('Runtime exception for Sentry')

        if action == 'http_error':
            raise HTTPError(500, 'HTTPError for Sentry')

        if action == 'message':
            self.get_sentry_logger().user['ip_address'] = '123.0.1.1'
            self.get_sentry_logger().capture_message('Message for Sentry')
        elif action == 'sample_rate':
            self.get_sentry_logger().extra['sample_rate'] = 0
            self.get_sentry_logger().capture_message('Sampled message')
        elif action == 'bad_sample_rate':
            self.get_sentry_logger().extra['sample_rate'] = 'bad'
            self.get_sentry_logger().capture_message('Sampled message')

    def finish(self, chunk=None):
        # delay page finish to make sure that sentry mock got the exception
        return asyncio.ensure_future(self.finish_delayed(chunk))

    async def finish_delayed(self, chunk):
        await asyncio.sleep(0.2)
        await super().finish(chunk)

    def initialize_sentry_logger(self, sentry_logger: SentryLogger):
        sentry_logger.user = {'id': '123456'}
        sentry_logger.extra = {'extra': 'data'}
