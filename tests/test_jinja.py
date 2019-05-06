import json
import unittest

from .instances import frontik_no_debug_app, frontik_re_app, frontik_test_app


class TestJinja(unittest.TestCase):
    def test_jinja_ok(self):
        response = frontik_test_app.get_page('jinja')
        self.assertTrue(response.headers['content-type'].startswith('text/html'))
        self.assertEqual(response.content, b'<html><body><b>1</b><i>2</i></body></html>')

    def test_jinja_custom_render(self):
        response = frontik_test_app.get_page('jinja?custom_render=true')
        self.assertTrue(response.headers['content-type'].startswith('text/html'))
        self.assertEqual(response.content, b'<html><body><b>custom1</b><i>custom2</i></body></html>')

    def test_jinja_custom_environment(self):
        response = frontik_re_app.get_page('jinja_custom_environment')
        self.assertEqual(response.content, b'<html><body>custom_env_function_value</body></html>')

    def test_jinja_no_environment(self):
        response = frontik_no_debug_app.get_page('jinja_no_environment')
        self.assertEqual(response.status_code, 500)

    def test_jinja_no_template_exists(self):
        response = frontik_test_app.get_page('jinja?template=no.html')
        self.assertEqual(response.status_code, 500)

        response = frontik_test_app.get_page('jinja?template=no.html', notpl=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers['content-type'].startswith('application/json'))

    def test_jinja_template_bad_data(self):
        response = frontik_test_app.get_page('jinja?template_error=true')
        self.assertEqual(response.status_code, 500)

        debug_response = frontik_test_app.get_page('jinja?template_error=true&debug')
        self.assertIn(b"&#39;req1&#39; is undefined", debug_response.content)

    def test_jinja_template_syntax_error(self):
        response = frontik_test_app.get_page('jinja?template=jinja-syntax-error.html')
        self.assertEqual(response.status_code, 500)

        debug_response = frontik_test_app.get_page('jinja?template=jinja-syntax-error.html&debug')
        self.assertIn(b"unexpected &#39;}&#39;", debug_response.content)

    def test_jinja_notpl(self):
        response = frontik_test_app.get_page('jinja', notpl=True)
        self.assertTrue(response.headers['content-type'].startswith('application/json'))

        data = json.loads(response.content)
        self.assertEqual(data['req1']['result'], '1')
        self.assertEqual(data['req2']['result'], '2')
