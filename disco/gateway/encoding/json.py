from disco.gateway.encoding.base import BaseEncoder
from disco.util.serializer import dumps as json_dumps, loads as json_loads


class JSONEncoder(BaseEncoder):
    TYPE = 'json'

    @staticmethod
    def encode(obj):
        return json_dumps(obj)

    @staticmethod
    def decode(obj):
        return json_loads(obj)
