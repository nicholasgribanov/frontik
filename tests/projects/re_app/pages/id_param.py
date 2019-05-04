from lxml import etree

from frontik.handler import XsltPageHandler


class Page(XsltPageHandler):
    async def get_page(self):
        self.set_xsl('id_param.xsl')
        self.doc.put(etree.Element('id', value=self.get_argument('id', 'wrong')))
