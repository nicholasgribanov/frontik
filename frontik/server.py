import asyncio
import importlib
import logging
import os.path
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import tornado.autoreload
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.options import parse_command_line, parse_config_file

from frontik.app import FrontikApplication
from frontik.loggers import bootstrap_core_logging
from frontik.options import options

if TYPE_CHECKING:  # pragma: no cover
    from typing import Type

log = logging.getLogger('server')


def parse_configs(*config_files: 'str') -> None:
    """Reads command line options / config file and bootstraps logging.
    """

    parse_command_line(final=False)

    if options.config:
        configs_to_read = [options.config]
    else:
        configs_to_read = config_files

    for config in configs_to_read:
        parse_config_file(config, final=False)

    # override options from config with command line options
    parse_command_line(final=False)

    bootstrap_core_logging()

    for config in configs_to_read:
        log.info('using config: %s', config)
        if options.autoreload:
            tornado.autoreload.watch(config)


def run_server(app: 'FrontikApplication'):
    """Starts Frontik server for an application"""

    if options.asyncio_task_threshold_sec is not None:
        import asyncio
        import reprlib

        reprlib.aRepr.maxother = 256
        old_run = asyncio.Handle._run

        def run(self):
            start_time = self._loop.time()
            old_run(self)
            duration = self._loop.time() - start_time
            if duration >= options.asyncio_task_threshold_sec:
                app.handle_long_asyncio_task(self, duration)

        asyncio.Handle._run = run  # type: ignore # https://github.com/python/mypy/issues/2427

    log.info('starting server on %s:%s', options.host, options.port)
    http_server = HTTPServer(app, xheaders=options.xheaders)
    http_server.bind(options.port, options.host, reuse_port=options.reuse_port)
    http_server.start()

    io_loop = IOLoop.current()

    if options.autoreload:
        tornado.autoreload.start(1000)

    def sigterm_handler(signum, frame):
        log.info('requested shutdown')
        log.info('shutting down server on %s:%d', options.host, options.port)
        io_loop.add_callback_from_signal(server_stop)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)

    def ioloop_is_running():
        return io_loop.asyncio_loop.is_running()

    def server_stop():
        http_server.stop()

        if ioloop_is_running():
            log.info('going down in %s seconds', options.stop_timeout)

            def ioloop_stop():
                if ioloop_is_running():
                    log.info('stopping IOLoop')
                    io_loop.stop()
                    log.info('stopped')

            io_loop.add_timeout(time.time() + options.stop_timeout, ioloop_stop)

    signal.signal(signal.SIGTERM, sigterm_handler)


def main(*config_files):
    parse_configs(*config_files)

    if options.app is None:
        log.exception('no frontik application present (`app` option is not specified)')
        sys.exit(1)

    log.info('starting application %s', options.app)

    try:
        module = importlib.import_module(options.app)
    except Exception:
        log.exception('failed to import application module "%s"', options.app)
        sys.exit(1)

    app_class_name = options.app_class

    if app_class_name and not hasattr(module, app_class_name):
        log.exception('application class "%s" not found', app_class_name)
        sys.exit(1)

    app_class = (
        getattr(module, app_class_name) if app_class_name else FrontikApplication
    )  # type: Type[FrontikApplication]

    try:
        ioloop = IOLoop.current()

        executor = ThreadPoolExecutor(options.common_executor_pool_size)
        ioloop.asyncio_loop.set_default_executor(executor)

        async def async_init():
            try:
                app = app_class(app_root=os.path.dirname(module.__file__), **options.as_dict())
                init_futures = app.default_init_futures + list(app.init_async())
                await asyncio.gather(*init_futures)
                run_server(app)

            except Exception:
                log.exception('failed to initialize application')
                sys.exit(1)

        ioloop.add_callback(lambda: asyncio.create_task(async_init()))
        ioloop.start()

    except BaseException:
        log.exception('failed to initialize application')
        sys.exit(1)
