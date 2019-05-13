import unittest

import requests

try:
    import raven
    has_raven = True
except Exception:
    has_raven = False

from .instances import frontik_re_app, frontik_test_app


@unittest.skipIf(not has_raven, 'raven library not found')
class TestSentryIntegration(unittest.TestCase):
    def test_sentry_exception(self):
        frontik_test_app.get_page('api/123/store', method=requests.delete)
        frontik_test_app.get_page('sentry_error?action=exception')

        exception = self._find_sentry_exception('Runtime exception for Sentry')
        self.assertEqual('error', exception['level'])
        self.assertIn('/sentry_error', exception['request']['url'])
        self.assertEqual('123456', exception['user']['id'])

    def test_sentry_message(self):
        frontik_test_app.get_page('api/123/store', method=requests.delete)
        frontik_test_app.get_page('sentry_error?action=message')

        message = self._find_sentry_message('Message for Sentry')
        self.assertEqual('info', message['level'])
        self.assertEqual('tests.projects.test_app.pages.sentry_error.Page.get_page', message['transaction'])
        self.assertEqual('GET', message['request']['method'])
        self.assertEqual('last version', message['release'])
        self.assertIn('/sentry_error', message['request']['url'])
        self.assertEqual('123456', message['user']['id'])

    def test_sentry_http_error(self):
        frontik_test_app.get_page('api/123/store', method=requests.delete)
        frontik_test_app.get_page('sentry_error?action=http_error')

        sentry_json = frontik_test_app.get_page_json('api/123/store')
        self.assertEqual({'exceptions': []}, sentry_json)

    def test_sentry_sample_rate(self):
        frontik_test_app.get_page('api/123/store', method=requests.delete)
        frontik_test_app.get_page('sentry_error?action=sample_rate')

        sentry_json = frontik_test_app.get_page_json('api/123/store')
        self.assertEqual({'exceptions': []}, sentry_json)

    def test_sentry_bad_sample_rate(self):
        frontik_test_app.get_page('api/123/store', method=requests.delete)
        frontik_test_app.get_page('sentry_error?action=bad_sample_rate')

        exception = self._find_sentry_message('Sampled message')
        self.assertIsNotNone(exception)

    def test_sentry_429(self):
        frontik_test_app.get_page('api/123/store', method=requests.delete)
        frontik_test_app.get_page('api/123/store?set_code=429', method=requests.post)

        frontik_test_app.get_page('sentry_error?action=message')
        sentry_json = frontik_test_app.get_page_json('api/123/store')
        self.assertEqual({'exceptions': []}, sentry_json)

        frontik_test_app.get_page('sentry_error?action=message')
        sentry_json = frontik_test_app.get_page_json('api/123/store')
        self.assertEqual({'exceptions': []}, sentry_json)

    def test_sentry_500(self):
        frontik_test_app.get_page('api/123/store', method=requests.delete)
        frontik_test_app.get_page('api/123/store?set_code=500', method=requests.post)
        frontik_test_app.get_page('sentry_error?action=message')

        sentry_json = frontik_test_app.get_page_json('api/123/store')
        self.assertEqual({'exceptions': []}, sentry_json)

    def test_sentry_not_configured(self):
        self.assertEqual('sentry logger is None', frontik_re_app.get_page_text('sentry_not_configured'))

    @staticmethod
    def _find_sentry_message(message):
        sentry_json = frontik_test_app.get_page_json('api/123/store')
        return next((e for e in sentry_json['exceptions'] if e['message'] == message), None)

    @staticmethod
    def _find_sentry_exception(exception):
        sentry_json = frontik_test_app.get_page_json('api/123/store')
        return next((e for e in sentry_json['exceptions'] if e['exception']['values'][-1]['value'] == exception), None)
