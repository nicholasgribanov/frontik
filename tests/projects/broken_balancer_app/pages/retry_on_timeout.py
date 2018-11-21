import time

import frontik.handler


class Page(frontik.handler.PageHandler):
    def delete_page(self):
        self.add_timeout(
            time.time() + 2, self.finish_group.add(self.check_finished(self.timeout_callback))
        )

    def timeout_callback(self):
        self.add_header('Content-Type', 'text/plain')
        self.text = 'result'
