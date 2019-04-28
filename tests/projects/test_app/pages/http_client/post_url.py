import re

from tornado.web import HTTPError

from frontik.handler import PageHandler
from frontik.util import any_to_bytes, any_to_unicode

FIELDS = {
    'fielda': 'hello',
    'fieldb': '',
    'field3': 'None',
    'field4': '0',
    'field5': 0,
    'field6': False,
    'field7': ['1', '3', 'jiji', bytes([1, 2, 3])]
}

FILES = {
    'field9': [{'filename': 'file0', 'body': b'\x10\x20\x30'}],
    'field10': [
        {'filename': 'file1', 'body': b'\x01\x02\x03'},
        {'filename': 'файл 01-12_25.abc', 'body': 'Ёконтент 123 !"№;%:?*()_+={}[]'}
    ]
}


class Page(PageHandler):
    def get_page(self):
        self.json.put(self.post_url(self.request.host, self.request.path, data=FIELDS, files=FILES))

    def post_page(self):
        body_parts = self.request.body.split(b'\r\n--')

        for part in body_parts:
            field_part = re.search(b'name="(?P<name>.+)"\r\n\r\n(?P<value>.*)', part)
            file_part = re.search(b'name="(?P<name>.+)"; filename="(?P<filename>.+)"\r\n'
                                  b'Content-Type: application/octet-stream\r\n\r\n(?P<value>.*)', part)

            actual_name = any_to_unicode(field_part.group('name'))
            actual_val = field_part.group('value')

            if field_part:
                expected_val = FIELDS[actual_name]
                is_list_field = isinstance(expected_val, list)

                if is_list_field and any(actual_val != any_to_bytes(x) for x in expected_val):
                    raise HTTPError(500)

                if not is_list_field and any_to_bytes(expected_val) != actual_val:
                    raise HTTPError(500)

            elif file_part:
                filename = file_part.group('filename')

                for file in FILES[actual_name]:
                    if any_to_bytes(file['filename']) == filename and any_to_bytes(file['body']) != actual_val:
                        raise HTTPError(500)
