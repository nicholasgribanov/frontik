from concurrent.futures import ThreadPoolExecutor
from functools import partial

from tornado.gen import coroutine
from tornado.ioloop import IOLoop

from frontik.handler import PageHandler
from frontik.request_context import context, RequestContext


def _callback(name, handler, *args):
    handler.json.put({name: RequestContext.get('handler_name') or context.get().handler_name})


class Page(PageHandler):
    def get_page(self):
        def _waited_callback(name):
            return self.finish_group.add(partial(_callback, name, self))

        self.json.put({'page': RequestContext.get('handler_name') or context.get().handler_name})

        self.add_callback(_waited_callback('callback'))

        with ThreadPoolExecutor(1) as tp:
            IOLoop.current().run_in_executor(tp, _waited_callback('executor'))

        self.add_future(self.run_coroutine(), self.finish_group.add_notification())

        future = self.post_url(self.request.host, self.request.uri)
        self.add_future(future, _waited_callback('future'))

    @coroutine
    def run_coroutine(self):
        self.json.put({'coroutine_before_yield': RequestContext.get('handler_name') or context.get().handler_name})

        yield self.post_url(self.request.host, self.request.uri)

        self.json.put({'coroutine_after_yield': RequestContext.get('handler_name') or context.get().handler_name})

    def post_page(self):
        pass

    def __repr__(self):
        return 'request_context'
