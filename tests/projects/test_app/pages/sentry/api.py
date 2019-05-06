import json
from datetime import datetime, timedelta

from frontik.handler import JsonPageHandler


class Page(JsonPageHandler):
    exceptions = []
    status = 200

    async def post_page(self):
        code = self.get_argument('set_code', None)
        if code is not None:
            Page.status = int(code)
            return

        if Page.status == 200:
            Page.exceptions.append(self.request.body)
        else:
            self.set_status(Page.status)

    async def get_page(self):
        self.json.put({
            'exceptions': [json.loads(e) for e in Page.exceptions]
        })

    async def delete_page(self):
        Page.exceptions = []
        Page.status = 200
        self.get_sentry_logger().sentry_client.transport._disabled_until = datetime.utcnow() - timedelta(seconds=10)
