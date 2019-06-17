import importlib
import logging
import os

from tornado.routing import Router

from frontik.handler import ErrorHandler

routing_logger = logging.getLogger('frontik.routing')

MAX_MODULE_NAME_LENGTH = os.pathconf('/', 'PC_PATH_MAX') - 1


class FileMappingRouter(Router):
    def __init__(self, module, application):
        self.application = application
        self.name = module.__name__

    def find_handler(self, request, **kwargs):
        url_parts = request.path.strip('/').split('/')

        if any('.' in part for part in url_parts):
            routing_logger.info('url contains "." character, using 404 page')
            return _get_application_404_handler_delegate(self.application, request)

        page_name = '.'.join(filter(None, url_parts))
        page_module_name = '.'.join(filter(None, (self.name, page_name)))
        routing_logger.debug('page module: %s', page_module_name)

        if len(page_module_name) > MAX_MODULE_NAME_LENGTH:
            routing_logger.info('page module name exceeds PATH_MAX (%s), using 404 page', MAX_MODULE_NAME_LENGTH)
            return _get_application_404_handler_delegate(self.application, request)

        try:
            page_module = importlib.import_module(page_module_name)
            routing_logger.debug('using %s from %s', page_module_name, page_module.__file__)
        except ImportError:
            routing_logger.warning('%s module not found', (self.name, page_module_name))
            return _get_application_404_handler_delegate(self.application, request)
        except Exception:
            routing_logger.exception('error while importing %s module', page_module_name)
            return _get_application_500_handler_delegate(self.application, request)

        if not hasattr(page_module, 'Page'):
            routing_logger.error('%s.Page class not found', page_module_name)
            return _get_application_404_handler_delegate(self.application, request)

        return self.application.get_handler_delegate(request, page_module.Page)


def _get_application_404_handler_delegate(application, request):
    handler_class, handler_kwargs = application.application_404_handler(request)
    return application.get_handler_delegate(request, handler_class, handler_kwargs)


def _get_application_500_handler_delegate(application, request):
    return application.get_handler_delegate(request, ErrorHandler, {'status_code': 500})
