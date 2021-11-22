from websocket import ABNF


class BaseEncoder:
    TYPE = None
    OPCODE = ABNF.OPCODE_TEXT

    @staticmethod
    def encode(obj):
        pass

    @staticmethod
    def decode(obj):
        pass
