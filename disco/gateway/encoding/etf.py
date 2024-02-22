from erlpack import ErlangTermDecoder, pack  # this feels like chaos
from websocket import ABNF

from disco.gateway.encoding.base import BaseEncoder

decoder = ErlangTermDecoder(encoding='utf-8')


class ETFEncoder(BaseEncoder):
    TYPE = 'etf'
    OPCODE = ABNF.OPCODE_BINARY

    @staticmethod
    def encode(obj):
        return pack(obj)

    @staticmethod
    def decode(obj):
        return decoder.loads(obj)
