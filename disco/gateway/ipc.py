from gevent import spawn as gevent_spawn
from gevent.event import AsyncResult as GeventAsyncResult
from random import choice as random_choice
from string import printable as string_printable
from weakref import WeakValueDictionary

from disco.util.logging import LoggingClass
from disco.util.serializer import dump_function, load_function


def get_random_str(size):
    return ''.join([random_choice(string_printable) for _ in range(size)])


class IPCMessageType:
    CALL_FUNC = 1
    GET_ATTR = 2
    EXECUTE = 3
    RESPONSE = 4


class GIPCProxy(LoggingClass):
    def __init__(self, obj, pipe):
        super(GIPCProxy, self).__init__()
        self.obj = obj
        self.pipe = pipe
        self.results = WeakValueDictionary()
        gevent_spawn(self.read_loop)

    def resolve(self, parts):
        base = self.obj
        for part in parts:
            base = getattr(base, part)

        return base

    def send(self, typ, data):
        self.pipe.put((typ, data))

    def handle(self, mtype, data):
        if mtype == IPCMessageType.CALL_FUNC:
            nonce, func, args, kwargs = data
            res = self.resolve(func)(*args, **kwargs)
            self.send(IPCMessageType.RESPONSE, (nonce, res))
        elif mtype == IPCMessageType.GET_ATTR:
            nonce, path = data
            self.send(IPCMessageType.RESPONSE, (nonce, self.resolve(path)))
        elif mtype == IPCMessageType.EXECUTE:
            nonce, raw = data
            func = load_function(raw)
            try:
                result = func(self.obj)
            except Exception:
                self.log.exception('Failed to EXECUTE: ')
                result = None

            self.send(IPCMessageType.RESPONSE, (nonce, result))
        elif mtype == IPCMessageType.RESPONSE:
            nonce, res = data
            if nonce in self.results:
                self.results[nonce].set(res)

    def read_loop(self):
        while True:
            try:
                mtype, data = self.pipe.get()
            except EOFError:
                return self.log.error('SHARD DOWN. MEDIC!')

            try:
                self.handle(mtype, data)
            except Exception:
                self.log.exception('Error in GIPCProxy:')

    def execute(self, func):
        nonce = get_random_str(32)
        raw = dump_function(func)
        self.results[nonce] = result = GeventAsyncResult()
        self.pipe.put((IPCMessageType.EXECUTE, (nonce, raw)))
        return result

    def get(self, path):
        nonce = get_random_str(32)
        self.results[nonce] = result = GeventAsyncResult()
        self.pipe.put((IPCMessageType.GET_ATTR, (nonce, path)))
        return result

    def call(self, path, *args, **kwargs):
        nonce = get_random_str(32)
        self.results[nonce] = result = GeventAsyncResult()
        self.pipe.put((IPCMessageType.CALL_FUNC, (nonce, path, args, kwargs)))
        return result
