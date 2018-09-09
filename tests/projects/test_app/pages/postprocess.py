from tornado import gen
from tornado.web import HTTPError

from frontik.handler import PageHandler


class ContentPostprocessor:
    def postprocessor(self, handler, tpl):
        raise gen.Return(tpl.replace('%%content%%', 'CONTENT'))


class Page(PageHandler):
    def get_page(self):
        if self.get_argument('raise_error', None) is not None:
            self.add_postprocessor(Page._pp1)

        if self.get_argument('finish', None) is not None:
            self.add_postprocessor(Page._pp2)

        if self.get_argument('header', None) is not None:
            self.add_template_postprocessor(Page._header_pp)

        if self.get_argument('content', None) is not None:
            content_postprocessor = ContentPostprocessor()
            self.add_template_postprocessor(content_postprocessor.postprocessor)

        self.set_template('postprocess.html')
        self.json.put({'content': '%%content%%'})

    def _early_pp_1(self):
        raise HTTPError(400)

    def _early_pp_2(self):
        self.finish('FINISH_IN_PP')

    def _header_pp(self, tpl):
        raise gen.Return(tpl.replace('%%header%%', 'HEADER'))
