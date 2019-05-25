from tornado.escape import to_unicode, utf8

from frontik.handler import JsonPageHandler

FIELDS = {
    'fielda': 'hello',
    'fieldb': '',
    'fieldc': None,
    'field3': 'None',
    'field4': '0',
    'field5': 0,
    'field6': False,
    'field7': ['1', '3', 'jiji', bytes([1, 2, 3])],
    'field8': [None],
}

FILES = {
    'field9': [{'filename': 'file0', 'body': b'\x10\x20\x30'}],
    'field10': [
        {'filename': 'file1', 'body': b'\x01\x02\x03'},
        {'filename': 'файл 01-12_25.abc', 'body': 'Ёконтент 123 !"№;%:?*()_+={}[]'}
    ]
}


class Page(JsonPageHandler):
    async def get_page(self):
        self.post_url(self.request.host, self.request.path, data=FIELDS, files=FILES, fail_fast=True)

    async def post_page(self):
        boundary = to_unicode(self.request.body.split(b'\r\n', maxsplit=1)[0])

        assert self.request.body == utf8(
            f'{boundary}\r\n'
            f'Content-Disposition: form-data; name="fielda"\r\n\r\nhello\r\n{boundary}\r\n'
            f'Content-Disposition: form-data; name="fieldb"\r\n\r\n\r\n{boundary}\r\n'
            f'Content-Disposition: form-data; name="field3"\r\n\r\nNone\r\n{boundary}\r\n'
            f'Content-Disposition: form-data; name="field4"\r\n\r\n0\r\n{boundary}\r\n'
            f'Content-Disposition: form-data; name="field5"\r\n\r\n0\r\n{boundary}\r\n'
            f'Content-Disposition: form-data; name="field6"\r\n\r\nFalse\r\n{boundary}\r\n'
            f'Content-Disposition: form-data; name="field7"\r\n\r\n1\r\n{boundary}\r\n'
            f'Content-Disposition: form-data; name="field7"\r\n\r\n3\r\n{boundary}\r\n'
            f'Content-Disposition: form-data; name="field7"\r\n\r\njiji\r\n{boundary}\r\n'
            f'Content-Disposition: form-data; name="field7"\r\n\r\n\x01\x02\x03\r\n{boundary}\r\n'
            f'Content-Disposition: form-data; name="field9"; filename="file0"\r\n'
            f'Content-Type: application/octet-stream\r\n\r\n\x10 0\r\n{boundary}\r\n'
            f'Content-Disposition: form-data; name="field10"; filename="file1"\r\n'
            f'Content-Type: application/octet-stream\r\n\r\n\x01\x02\x03\r\n{boundary}\r\n'
            f'Content-Disposition: form-data; name="field10"; filename="файл 01-12_25.abc"\r\n'
            f'Content-Type: application/octet-stream\r\n\r\nЁконтент 123 !"№;%:?*()_+={{}}[]\r\n{boundary}--\r\n'
        )
