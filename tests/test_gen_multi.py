import unittest

from .instances import frontik_test_app


class TestGenMulti(unittest.TestCase):
    def test_group(self):
        json = frontik_test_app.get_page_json('gen_multi')
        self.assertEqual(
            json,
            {
                '1': {'1': 'yay'},
                '2': {'2': 'yay'},
                '3': {'3': 'yay'},
            }
        )

    def test_group_request_fail(self):
        json = frontik_test_app.get_page_json('gen_multi?fail_request=true')
        self.assertEqual(
            json,
            {
                '1': {'1': 'yay'},
                '2': {'2': 'yay'},
                '3': {'error': {'reason': 'HTTP 400: Bad Request', 'code': 400}},
            }
        )

    def test_group_callback_fail(self):
        response = frontik_test_app.get_page('gen_multi?fail_callback=true')
        self.assertEqual(response.status_code, 500)
