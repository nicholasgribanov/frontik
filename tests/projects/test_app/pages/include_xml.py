from frontik.handler import XmlPageHandler


class Page(XmlPageHandler):
    async def get_page(self):
        self.doc.put(self.xml_from_file('aaa.xml'))
