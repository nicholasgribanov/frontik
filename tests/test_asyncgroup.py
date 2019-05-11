import logging
from functools import partial

from tornado.concurrent import Future
from tornado.testing import gen_test, AsyncTestCase, ExpectLog
from tornado.web import app_log

from frontik.futures import async_logger, AsyncGroup


logging.root.setLevel(logging.NOTSET)


class TestAsyncGroup(AsyncTestCase):
    @gen_test
    def test_callbacks(self):
        data = []

        def callback2():
            data.append(2)

        def finish_callback():
            self.assertEqual(data, [1, 2])
            data.append(3)

        ag = AsyncGroup(finish_callback)
        cb1 = ag.add(partial(data.append, 1))
        cb2 = ag.add(callback2)

        self.assertFalse(ag._finished)

        ag.try_finish()

        self.assertFalse(ag._finished)

        cb1()

        self.assertFalse(ag._finished)

        cb2()

        self.assertFalse(ag._finished)
        self.assertEqual(data, [1, 2])

        yield ag.get_finish_future()

        self.assertTrue(ag._finished)
        self.assertEqual(data, [1, 2, 3])

    @gen_test
    def test_notifications(self):
        f = Future()
        ag = AsyncGroup(partial(f.set_result, True))
        not1 = ag.add_notification()
        not2 = ag.add_notification()

        self.assertFalse(ag._finished)

        not1()

        self.assertFalse(ag._finished)

        not2('params', are='ignored')

        self.assertFalse(ag._finished)

        yield ag.get_finish_future()

        self.assertTrue(ag._finished)
        self.assertTrue(f.result())

        with ExpectLog(async_logger, r'.*trying to finish already finished AsyncGroup\(name=None, finished=True\)'):
            ag.finish()

    def test_finish(self):
        f = Future()
        ag = AsyncGroup(partial(f.set_result, True))

        self.assertEqual(ag._finished, False)

        ag.add_notification()
        ag.finish()

        self.assertEqual(ag._finished, True)
        self.assertEqual(f.result(), True)

    def test_exception_in_first(self):
        def callback1():
            raise Exception('callback1 error')

        def callback2():
            self.fail('callback2 should not be called')

        def finish_callback():
            self.fail('finish_callback should not be called')

        ag = AsyncGroup(finish_callback, name='test_group')
        cb1 = ag.add(callback1)
        cb2 = ag.add(callback2)

        self.assertRaises(Exception, cb1)
        self.assertEqual(ag._finished, True)

        with ExpectLog(async_logger, r'.*ignoring executing callback in AsyncGroup\(name=test_group, finished=True\)'):
            cb2()

        self.assertEqual(ag._finished, True)

    def test_exception_in_last(self):
        def callback2():
            raise Exception('callback1 error')

        def finish_callback():
            self.fail('finish_callback should not be called')

        ag = AsyncGroup(finish_callback, name='test_group')
        cb1 = ag.add(lambda: None)
        cb2 = ag.add(callback2)

        cb1()

        with ExpectLog(async_logger, r'.*aborting AsyncGroup\(name=test_group, finished=False\)'):
            self.assertRaises(Exception, cb2)

        self.assertEqual(ag._finished, True)

    @gen_test
    def test_exception_in_final(self):
        def finish_callback():
            raise Exception('callback1 error')

        ag = AsyncGroup(finish_callback)

        with ExpectLog(app_log, r'.*Exception in callback.*AsyncGroup\.finish.*'):
            ag.try_finish()
            yield ag.get_finish_future()
            self.assertEqual(ag._finished, True)
