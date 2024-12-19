from gevent import getcurrent as gevent_getcurrent


class ThreadLocal:
    ___slots__ = ['storage']

    def __init__(self):
        self.storage = {}

    def get(self):
        if gevent_getcurrent() not in self.storage:
            self.storage[gevent_getcurrent()] = {}
        return self.storage[gevent_getcurrent()]

    def drop(self):
        if gevent_getcurrent() in self.storage:
            del self.storage[gevent_getcurrent()]

    def __contains__(self, key):
        return key in self.get()

    def __getitem__(self, item):
        return self.get()[item]

    def __setitem__(self, item, value):
        self.get()[item] = value
