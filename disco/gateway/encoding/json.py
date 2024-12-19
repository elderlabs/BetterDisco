try:
    from ujson import dumps as json_dumps, loads as json_loads
except ImportError:
    from json import dumps as json_dumps, loads as json_loads

from disco.gateway.encoding.base import BaseEncoder


class JSONEncoder(BaseEncoder):
    TYPE = 'json'

    @staticmethod
    def encode(obj):
        return json_dumps(obj)

    @staticmethod
    def decode(obj):
        return json_loads(obj)
