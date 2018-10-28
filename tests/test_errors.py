# coding=utf-8

import unittest

from .instances import frontik_re_app, frontik_test_app


class TestHttpError(unittest.TestCase):
    def test_raise_200(self):
        response = frontik_test_app.get_page('http_error?code=200')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'<html><title>200: OK</title><body>200: OK</body></html>')

    def test_raise_401(self):
        response = frontik_test_app.get_page('http_error?code=401')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.raw.reason, 'Unauthorized')
        self.assertEqual(response.headers['content-type'], 'text/html; charset=UTF-8')
        self.assertEqual(
            response.content,
            b'<html><title>401: Unauthorized</title><body>401: Unauthorized</body></html>'
        )

    def test_raise_with_unknown_code(self):
        response = frontik_test_app.get_page('http_error?code=599')
        self.assertEqual(response.status_code, 503)

    def test_finish_200(self):
        response = frontik_test_app.get_page('finish?code=200&throw=false')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'success')

    def test_finish_401(self):
        response = frontik_test_app.get_page('finish?code=401&throw=false')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content, b'success')

    def test_finish_with_unknown_code(self):
        response = frontik_test_app.get_page('finish?code=599&throw=false')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b'success')

    def test_finish_exception_200(self):
        response = frontik_test_app.get_page('finish?code=200&throw=true')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'success')

    def test_finish_exception_401(self):
        response = frontik_test_app.get_page('finish?code=401&throw=true')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content, b'success')

    def test_finish_exception_with_unknown_code(self):
        response = frontik_test_app.get_page('finish?code=599&throw=true')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b'success')

    def test_http_error_xml(self):
        response = frontik_test_app.get_page('xsl/simple?raise=true')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, b'<html><body>\n<h1>ok</h1>\n<h1>not ok</h1>\n</body></html>\n')

    def test_http_error_text(self):
        response = frontik_test_app.get_page('test_exception_text')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b'This is just a plain text')

    def test_http_error_json(self):
        response = frontik_test_app.get_page('test_exception_json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, b'{"reason": "bad argument"}')

    def test_write_error(self):
        response = frontik_test_app.get_page('write_error')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.content, b'{"write_error": true}')

    def test_write_error_exception(self):
        response = frontik_test_app.get_page('write_error?fail_write_error=true')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.content, b'')
