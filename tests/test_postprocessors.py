import unittest

from .instances import frontik_test_app


class TestPostprocessors(unittest.TestCase):
    def test_no_postprocessors(self):
        response = frontik_test_app.get_page('postprocess')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'<html><h1>%%header%%</h1>%%content%%</html>')

    def test_postprocessors_raise_error(self):
        response = frontik_test_app.get_page('postprocess?raise_error')
        self.assertEqual(response.status_code, 400)

    def test_postprocessors_finish(self):
        response = frontik_test_app.get_page_text('postprocess?finish')
        self.assertEqual(response, 'FINISH_IN_PP')

    def test_template_postprocessors_finish(self):
        response = frontik_test_app.get_page_text('postprocess?template_finish')
        self.assertEqual(response, 'FINISH_IN_TEMPLATE_PP')

    def test_render_postprocessors_single(self):
        response = frontik_test_app.get_page('postprocess?header')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'<html><h1>HEADER</h1>%%content%%</html>')

    def test_render_postprocessors_multiple(self):
        response = frontik_test_app.get_page('postprocess?header&content')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'<html><h1>HEADER</h1>CONTENT</html>')

    def test_render_postprocessors_notpl(self):
        response = frontik_test_app.get_page('postprocess?content&notpl')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'{"content": "CONTENT"}')
