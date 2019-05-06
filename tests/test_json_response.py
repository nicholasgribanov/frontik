import json
import unittest

from .instances import frontik_test_app


class TestJsonResponse(unittest.TestCase):
    def test_json(self):
        response = frontik_test_app.get_page('json_page')
        self.assertEqual('text/json', response.headers['content-type'])

        data = json.loads(response.content)
        self.assertEqual(data['req1']['result'], 'OK')
        self.assertEqual(data['req2']['result'], 'OK')

    def test_invalid_json(self):
        response = frontik_test_app.get_page('json_page?invalid=true')
        self.assertEqual('text/json', response.headers['content-type'])

        data = json.loads(response.content)
        self.assertEqual(data['req1']['error']['reason'], 'invalid json')
        self.assertEqual(data['req2']['result'], 'OK')
