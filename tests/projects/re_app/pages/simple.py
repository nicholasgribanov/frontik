from lxml import etree

from frontik.handler import XsltPageHandler


class Page(XsltPageHandler):
    async def get_page(self):
        self.set_xsl('simple.xsl')
        self.doc.put(etree.Element('ok'))
