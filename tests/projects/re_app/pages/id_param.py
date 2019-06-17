from lxml import etree

from frontik.handler import XsltPageHandler


class Page(XsltPageHandler):
    async def get_page(self, id_param):
        self.set_xsl('id_param.xsl')
        self.doc.put(etree.Element('id', value=id_param))
