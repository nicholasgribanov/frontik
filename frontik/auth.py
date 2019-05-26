import base64
import http.client
from typing import TYPE_CHECKING

from tornado.escape import to_unicode
from tornado.web import Finish

if TYPE_CHECKING:  # pragma: no cover
    from tornado.httputil import HTTPServerRequest

    from frontik.handler import PageHandler

DEBUG_AUTH_HEADER_NAME = 'Frontik-Debug-Auth'


class DebugUnauthorizedError(Finish):
    pass


def check_debug_auth(handler: 'PageHandler', login: str, password: str) -> None:
    debug_auth_header = handler.request.headers.get(DEBUG_AUTH_HEADER_NAME)
    if debug_auth_header is not None:
        debug_access = (debug_auth_header == f'{login}:{password}')
        if not debug_access:
            handler.set_header('WWW-Authenticate', f'{DEBUG_AUTH_HEADER_NAME}-Header realm="Secure Area"')
            handler.set_status(http.client.UNAUTHORIZED)
            raise DebugUnauthorizedError()
    else:
        debug_access = _parse_basic_auth(handler.request, login, password)
        if not debug_access:
            handler.set_header('WWW-Authenticate', 'Basic realm="Secure Area"')
            handler.set_status(http.client.UNAUTHORIZED)
            raise DebugUnauthorizedError()


def _parse_basic_auth(request: 'HTTPServerRequest', login: str, password: str) -> bool:
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Basic '):
        _, auth_b64 = auth_header.split(' ', maxsplit=1)
        try:
            decoded_value = to_unicode(base64.b64decode(auth_b64))
        except ValueError:
            return False

        given_login, _, given_passwd = decoded_value.partition(':')
        return login == given_login and password == given_passwd

    return False
