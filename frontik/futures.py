from tornado.ioloop import IOLoop
from tornado.concurrent import Future


def future_fold(future, result_mapper=None, exception_mapper=None):
    """
    Creates a new future with result or exception processed by result_mapper and exception_mapper.

    If result_mapper or exception_mapper raises an exception, it will be set as an exception for the resulting future.
    Any of the mappers can be None — then the result or exception is left as is.
    """

    res_future = Future()

    def default_exception_mapper(error):
        raise error

    def _process(func, value):
        try:
            processed = func(value) if func is not None else value
        except Exception as e:
            res_future.set_exception(e)
            return
        res_future.set_result(processed)

    if not callable(exception_mapper):
        exception_mapper = default_exception_mapper

    def _on_ready(wrapped_future):
        exception = wrapped_future.exception()
        if exception is not None:
            _process(exception_mapper, exception)
        else:
            _process(result_mapper, future.result())

    IOLoop.current().add_future(future, callback=_on_ready)
    return res_future


def future_map(future, func):
    return future_fold(future, result_mapper=func)


def future_map_exception(future, func):
    return future_fold(future, exception_mapper=func)
