import socket
import unittest

from tornado.escape import to_unicode

from frontik.loggers.statsd import has_statsd

from .instances import frontik_test_app, FrontikTestInstance


@unittest.skipIf(not has_statsd, 'aiostatsd library not found')
class TestStatsd(unittest.TestCase):
    def test_send_to_statsd(self):
        statsd_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        statsd_socket.settimeout(0.1)
        statsd_socket.bind(('', 0))

        port = statsd_socket.getsockname()[1]

        test_app = FrontikTestInstance(
            './frontik-test --app=tests.projects.test_app --config=tests/projects/frontik_debug.cfg '
            '--statsd_host=127.0.0.1 --statsd_port={} --statsd_flush_interval_sec=0'.format(port)
        )

        test_app.get_page('statsd')
        test_app.stop()

        metrics = []
        try:
            chunk = statsd_socket.recv(1024 * 24)
            while chunk:
                metrics.append(to_unicode(chunk))
                chunk = statsd_socket.recv(1024 * 24)
        except socket.timeout:
            pass
        finally:
            statsd_socket.close()

        metrics = '\n'.join(metrics).split('\n')

        self.assertIn('count_metric.app_is_tests-projects-test_app.tag1_is_tag1.tag2_is_tag2:10|c', metrics)
        self.assertIn('gauge_metric.app_is_tests-projects-test_app.tag_is_tag3:100|g', metrics)
        self.assertIn('time_metric.app_is_tests-projects-test_app.tag_is_tag4:1000|ms', metrics)
