from frontik.handler import PageHandler
from frontik.preprocessors import preprocessor


@preprocessor
async def pp(handler):
    handler.json.put({'ok': True})


class Page(PageHandler):
    @pp
    def get_page(self):
        pass
