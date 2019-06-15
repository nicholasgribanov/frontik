import mimetypes
import os.path
import re
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from tornado.escape import to_unicode, utf8

from frontik import media_types

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Dict, Iterable, List, Optional, Tuple

    from frontik.handler import PageHandler


def any_to_unicode(s: 'Any') -> str:
    if isinstance(s, bytes):
        return to_unicode(s)

    return str(s)


def any_to_bytes(s: 'Any') -> bytes:
    if isinstance(s, str):
        return utf8(s)
    elif isinstance(s, bytes):
        return s

    return utf8(str(s))


def make_qs(query_args: 'Dict[Any, Any]') -> str:
    return urlencode([(k, v) for k, v in query_args.items() if v is not None], doseq=True)


def make_body(data):
    return make_qs(data) if isinstance(data, dict) else any_to_bytes(data)


def make_url(url: str, **query_args: 'Dict[Any, Any]') -> str:
    """
    Builds URL from base part and query arguments passed as kwargs.
    Returns unicode string
    """
    scheme, netloc, path, query, fragment = urlsplit(url)
    if query:
        qs = parse_qs(query, keep_blank_values=True)  # type: Dict[Any, Any]
    else:
        qs = {}

    qs.update(query_args)

    return urlunsplit((scheme, netloc, path, make_qs(qs), fragment))


def _decode_bytes_from_charset(string: bytes, charsets: 'Iterable[str]' = ('cp1251',)) -> str:
    decoded_body = None
    for c in charsets:
        try:
            decoded_body = string.decode(c)
            break
        except UnicodeError:
            continue

    if decoded_body is None:
        raise UnicodeError('Could not decode string (tried: {})'.format(', '.join(charsets)))

    return decoded_body


_BOUNDARY = utf8(uuid4().hex)


def make_mfd(fields: 'Dict[str, Any]', files: 'Dict[str, Any]') -> 'Tuple[bytes, bytes]':
    """
    Constructs request body in multipart/form-data format

    fields :: { field_name : field_value }
    files :: { field_name: [{ "filename" : fn, "body" : bytes }]}
    """

    body = []  # type: List[bytes]

    for name, data in fields.items():
        if isinstance(data, list):
            for value in data:
                if value is not None:
                    body.extend(_create_field(name, value))

        elif data is not None:
            body.extend(_create_field(name, data))

    for name, data in files.items():
        for file in data:
            body.extend(_create_file_field(
                name, file['filename'], file['body'], file.get('content_type', 'application/unknown')
            ))

    body.extend([b'--', _BOUNDARY, b'--\r\n'])
    content_type = b'multipart/form-data; boundary=' + _BOUNDARY

    return b''.join(body), content_type


def _addslashes(text):
    for s in (b'\\', b'"'):
        if s in text:
            text = text.replace(s, b'\\' + s)
    return text


def _create_field(name, data):
    name = _addslashes(any_to_bytes(name))

    return [
        b'--', _BOUNDARY,
        b'\r\nContent-Disposition: form-data; name="', name,
        b'"\r\n\r\n', any_to_bytes(data), b'\r\n'
    ]


def _create_file_field(name, filename, data, content_type):
    if content_type == 'application/unknown':
        content_type = mimetypes.guess_type(filename)[0] or media_types.APPLICATION_OCTET_STREAM
    else:
        content_type = content_type.replace('\n', ' ').replace('\r', ' ')

    name = _addslashes(any_to_bytes(name))
    filename = _addslashes(any_to_bytes(filename))

    return [
        b'--', _BOUNDARY,
        b'\r\nContent-Disposition: form-data; name="', name, b'"; filename="', filename,
        b'"\r\nContent-Type: ', any_to_bytes(content_type),
        b'\r\n\r\n', any_to_bytes(data), b'\r\n'
    ]


def get_cookie_or_url_param_value(handler: 'PageHandler', param_name: 'str') -> 'Optional[str]':
    return handler.get_argument(param_name, handler.get_cookie(param_name, None))


def reverse_regex_named_groups(pattern, *args, **kwargs):
    class GroupReplacer:
        def __init__(self, args, kwargs):
            self.args, self.kwargs = args, kwargs
            self.current_arg = 0

        def __call__(self, match):
            value = ''
            named_group = re.search(r'^\?P<(\w+)>(.*?)$', match.group(1))

            if named_group:
                group_name = named_group.group(1)
                if group_name in self.kwargs:
                    value = self.kwargs[group_name]
                elif self.current_arg < len(self.args):
                    value = self.args[self.current_arg]
                    self.current_arg += 1
                else:
                    raise ValueError('Cannot reverse regex: required number of arguments not found')

            return any_to_unicode(value)

    result = re.sub(r'\(([^)]+)\)', GroupReplacer(args, kwargs), to_unicode(pattern))
    return result.replace('^', '').replace('$', '')


def get_abs_path(root_path: str, relative_path: 'Optional[str]') -> str:
    if not relative_path:
        return root_path
    elif os.path.isabs(relative_path):
        return relative_path

    return os.path.normpath(os.path.join(root_path, relative_path))
