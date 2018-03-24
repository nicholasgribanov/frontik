import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        from frontik.producers.xml_producer import touch_xsl
        touch_xsl()
