from gevent import sleep as gevent_sleep, spawn as gevent_spawn
from gevent.lock import Semaphore as GeventSemaphore


class SimpleLimiter:
    def __init__(self, total, per):
        self.total = total
        self.per = per
        self._lock = GeventSemaphore(total)

        self.count = 0
        self.reset_at = 0
        self.event = None

    def check(self):
        self._lock.acquire()

        def _release_lock():
            gevent_sleep(self.per)
            self._lock.release()

        gevent_spawn(_release_lock)
