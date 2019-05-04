import json
from typing import Any, Type

from tornado.concurrent import Future


def _encode_value(v: Any) -> Any:
    def _encode_iterable(l):
        return [_encode_value(v) for v in l]

    def _encode_dict(d):
        return {k: _encode_value(v) for k, v in d.items()}

    if isinstance(v, dict):
        return _encode_dict(v)

    elif isinstance(v, (set, frozenset, list, tuple)):
        return _encode_iterable(v)

    elif isinstance(v, Future):
        if v.done():
            return _encode_value(v.result())

        return None

    elif hasattr(v, 'to_dict'):
        return v.to_dict()

    return v


class FrontikJsonEncoder(json.JSONEncoder):
    """
    This encoder supports additional value types:
    * sets and frozensets
    * datetime.date objects
    * objects with `to_dict()` method
    * objects with `to_json_value()` method
    * `Future` objects (only if the future is resolved)
    """
    def default(self, obj):
        return _encode_value(obj)


class JsonBuilder:
    __slots__ = ('_data', '_encoder', 'root_node')

    def __init__(self, json_encoder: Type[FrontikJsonEncoder] = None):
        self._data = []
        self._encoder = json_encoder

    def put(self, chunk) -> 'JsonBuilder':
        """Append a chunk of data to JsonBuilder."""
        self._data.append(chunk)
        return self

    def is_empty(self) -> bool:
        return len(self._data) == 0

    def clear(self):
        self._data = []

    def replace(self, chunk) -> 'JsonBuilder':
        self.clear()
        self.put(chunk)
        return self

    def to_dict(self) -> dict:
        """ Return plain dict from all data appended to JsonBuilder """
        return _encode_value(self._concat_chunks())

    def _concat_chunks(self) -> dict:
        result = {}
        for chunk in self._data:
            if isinstance(chunk, Future) or hasattr(chunk, 'to_dict'):
                chunk = _encode_value(chunk)

            if chunk is not None:
                result.update(chunk)

        return result

    def to_string(self) -> str:
        if self._encoder is None:
            return json.dumps(self._concat_chunks(), cls=FrontikJsonEncoder, ensure_ascii=False)

        return json.dumps(self._concat_chunks(), cls=self._encoder, ensure_ascii=False)
