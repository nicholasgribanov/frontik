from lxml import etree

import frontik.doc
from frontik.handler import XmlPageHandler


class Page(XmlPageHandler):
    async def get_page(self):
        self.doc.put(frontik.doc.Doc())
        self.doc.put(etree.Element('element', name='Test element'))
        self.doc.put(frontik.doc.Doc(root_node='ok'))
