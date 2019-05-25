import unittest

from .instances import frontik_broken_config_app, frontik_broken_init_async_app, FrontikTestInstance


class TestBrokenApp(unittest.TestCase):
    def test_broken_config(self):
        with self.assertRaises(AssertionError):
            frontik_broken_config_app.start()

    def test_broken_init_async(self):
        with self.assertRaises(AssertionError):
            frontik_broken_init_async_app.start()

    def test_no_app_option(self):
        with self.assertRaises(AssertionError):
            test_app = FrontikTestInstance('./frontik-test --config=tests/projects/frontik_debug.cfg --stderr_log=true')
            test_app.start()

    def test_nonexistent_app_option(self):
        with self.assertRaises(AssertionError):
            test_app = FrontikTestInstance(
                './frontik-test --config=tests/projects/frontik_debug.cfg --app=frontik.no.app --stderr_log=true'
            )
            test_app.start()

    def test_nonexistent_app_class_option(self):
        with self.assertRaises(AssertionError):
            test_app = FrontikTestInstance(
                './frontik-test --config=tests/projects/frontik_debug.cfg --stderr_log=true '
                '--app=tests.projects.test_app --app_class=NoApplication'
            )
            test_app.start()
