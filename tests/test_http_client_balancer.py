# coding=utf-8

import unittest

# noinspection PyUnresolvedReferences
import frontik.options

from frontik.http_client import Upstream, Server


def _total_weight(upstream):
    return sum(server.weight for server in upstream.servers if server is not None)


def _total_requests(upstream):
    return sum(server.requests for server in upstream.servers if server is not None)


class TestHttpClientBalancer(unittest.TestCase):
    @staticmethod
    def _upstream(servers):
        return Upstream('upstream', {}, servers)

    def test_create(self):
        upstream = self._upstream([Server('1', 1), Server('2', 1)])

        self.assertEqual(len(upstream.servers), 2)
        self.assertEqual(_total_weight(upstream), 2)

    def test_add_server(self):
        servers = [Server('1', 1), Server('2', 1)]
        upstream = self._upstream(servers)

        servers.append(Server('3', 1))
        upstream.update({}, servers)

        self.assertEqual(len(upstream.servers), 3)
        self.assertEqual(_total_weight(upstream), 3)

    def test_remove_server(self):
        upstream = self._upstream([Server('1', 1), Server('2', 1)])
        upstream.update({}, [Server('1', 1)])

        self.assertEqual(len(upstream.servers), 2)
        self.assertEqual(len([server for server in upstream.servers if server is not None]), 1)
        self.assertEqual(_total_weight(upstream), 1)

    def test_replace_server(self):
        upstream = self._upstream([Server('1', 1), Server('2', 1)])
        upstream.update({}, [Server('1', 2), Server('2', 5)])

        self.assertEqual(len(upstream.servers), 2)
        self.assertEqual(_total_weight(upstream), 7)

    def test_remove_add_server(self):
        upstream = self._upstream([Server('1', 1), Server('2', 1)])
        upstream.update({}, [Server('2', 2), Server('3', 5)])

        self.assertEqual(len(upstream.servers), 2)
        self.assertEqual(_total_weight(upstream), 7)

    def test_borrow_server(self):
        upstream = self._upstream([Server('1', 2), Server('2', 1)])

        _, address = upstream.borrow_server()
        self.assertEqual(address, '1')

        _, address = upstream.borrow_server()
        self.assertEqual(address, '2')

        _, address = upstream.borrow_server()
        self.assertEqual(address, '1')

        _, address = upstream.borrow_server()
        self.assertEqual(address, '1')

        self.assertEqual(_total_requests(upstream), 4)

    def test_borrow_return_server(self):
        upstream = self._upstream([Server('1', 1), Server('2', 5)])

        _, address = upstream.borrow_server()
        self.assertEqual(address, '1')

        fd, address = upstream.borrow_server()
        self.assertEqual(address, '2')

        upstream.return_server(fd)

        _, address = upstream.borrow_server()
        self.assertEqual(address, '2')

        self.assertEqual(_total_requests(upstream), 2)

    def test_replace_in_process(self):
        upstream = self._upstream([Server('1', 1), Server('2', 5)])

        fd, address = upstream.borrow_server()
        self.assertEqual(address, '1')

        _, address = upstream.borrow_server()
        self.assertEqual(address, '2')

        server = Server('3', 1)
        upstream.update({}, [Server('1', 1), server])

        self.assertEqual(_total_requests(upstream), 1)

        upstream.return_server(fd)

        self.assertEqual(_total_requests(upstream), 0)
        self.assertEqual(server.requests, 0)

        _, address = upstream.borrow_server()
        self.assertEqual(address, '3')