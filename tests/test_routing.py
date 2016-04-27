# coding=utf-8

import unittest

from . import py3_skip
from .instances import frontik_re_app, frontik_test_app


class TestRouting(unittest.TestCase):
    @py3_skip
    def test_regexp(self):
        html = frontik_re_app.get_page_text('not_simple')
        self.assertIn('ok', html)

    @py3_skip
    def test_file_mapping(self):
        html = frontik_test_app.get_page_text('simple_xml')
        self.assertIn('ok', html)

    @py3_skip
    def test_fallback_file_mapping(self):
        html = frontik_re_app.get_page_text('simple')
        self.assertIn('ok', html)

    @py3_skip
    def test_extra_slash_in_regex(self):
        """Routes specified with regexps should match precisely"""
        self.assertEqual(frontik_re_app.get_page('//not_simple').status_code, 404)

    @py3_skip
    def test_extra_slash_in_mapping(self):
        """Routes specified as mappings to filesystem can contain extra slashes"""
        self.assertEqual(frontik_re_app.get_page('//simple').status_code, 200)
        self.assertEqual(frontik_test_app.get_page('//nested///nested//////nested').status_code, 200)

    @py3_skip
    def test_rewrite_single(self):
        html = frontik_re_app.get_page_text('id/some')
        self.assertIn('some', html)

    @py3_skip
    def test_rewrite_multiple(self):
        values = ('some', 'another')
        html = frontik_re_app.get_page_text('id/{}'.format(','.join(values)))
        self.assertTrue(all(map(html.find, values)))

    @py3_skip
    def test_error_on_import(self):
        response = frontik_test_app.get_page('error_on_import')
        self.assertEqual(response.status_code, 500)

    @py3_skip
    def test_regex_404(self):
        response = frontik_re_app.get_page('not_matching_regex')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content, '<html><title>404: Not Found</title><body>404: Not Found</body></html>')

    @py3_skip
    def test_regex_exception_on_init(self):
        self.assertEqual(frontik_re_app.get_page('exception_on_init').status_code, 500)

    @py3_skip
    def test_regex_httperror_on_init(self):
        self.assertEqual(frontik_re_app.get_page('httperror_on_init').status_code, 401)

    @py3_skip
    def test_filemapping_404(self):
        self.assertEqual(frontik_test_app.get_page('no_page').status_code, 404)

    @py3_skip
    def test_filemapping_404_on_dot_in_url(self):
        self.assertEqual(frontik_test_app.get_page('/nested/nested.nested').status_code, 404)

    @py3_skip
    def test_filemapping_custom_404(self):
        response = frontik_re_app.get_page('inexistent_page')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content, '404')
