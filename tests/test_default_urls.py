import json
import unittest

from .instances import frontik_re_app, frontik_test_app


class TestDefaultUrls(unittest.TestCase):
    def test_version(self):
        json = frontik_test_app.get_page_json('version')
        self.assertEqual('last version', json['tests.projects.test_app'])

    def test_no_version(self):
        json = frontik_re_app.get_page_json('version')
        self.assertEqual('unknown', json['tests.projects.re_app'])

    def test_status(self):
        response = frontik_test_app.get_page('status')

        self.assertTrue(response.headers['Content-Type'].startswith('application/json'))

        json_response = json.loads(response.content)
        self.assertIn('uptime', json_response)
        self.assertIn('datacenter', json_response)
