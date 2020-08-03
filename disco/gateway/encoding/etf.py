from websocket import ABNF

from disco.gateway.encoding.base import BaseEncoder

from earl import unpack, pack


class ETFEncoder(BaseEncoder):
    TYPE = 'etf'
    OPCODE = ABNF.OPCODE_BINARY

    @staticmethod
    def encode(obj):
        return pack(obj)

    @staticmethod
    def decode(obj):
        return unpack(obj, encoding='utf-8', encode_binary_ext=True)
