from collections import defaultdict
from gevent import spawn as gevent_spawn
from gevent.event import AsyncResult as GeventAsyncResult
from gevent.pool import Pool as GeventPool
from gevent.queue import Queue as GeventQueue

from disco.util.logging import LoggingClass


class Priority:
    # BEFORE is the most dangerous priority level. Every event that flows through
    #  the given emitter instance will be dispatched _sequentially_ to all BEFORE
    #  handlers. Until these before handlers complete execution, no other event
    #  will be allowed to continue. Any exceptions raised will be ignored.
    BEFORE = 10000

    # STATE should be used for updating state objects alone. Never anything else.
    STATE = 20000

    # AFTER has the same behavior as before with regard to dispatching events,
    #  with the one difference being it executes after all the BEFORE listeners.
    AFTER = 30000

    # SEQUENTIAL guarantees that all events your handler receives will be ordered
    #  when looked at in isolation. SEQUENTIAL handlers will not block other handlers,
    #  but do use a queue internally and thus can fall behind.
    SEQUENTIAL = 40000

    # NONE provides no guarantees around the ordering or execution of events, sans
    #  that BEFORE handlers will always complete before any NONE handlers are called.
    NONE = 50000

    ALL = {BEFORE, STATE, AFTER, SEQUENTIAL, NONE}


class Event:
    def __init__(self, parent, data):
        self.parent = parent
        self.data = data

    def __getattr__(self, name):
        if hasattr(self.data, name):
            return getattr(self.data, name)
        raise AttributeError

    def clone(self):
        new = object.__new__(self.__class__)
        new.parent = self.parent
        new.data = self.data
        return new


class EmitterSubscription:
    def __init__(self, events, callback, priority=Priority.NONE, conditional=None, metadata=None, max_queue_size=8192):
        self.events = events
        self.callback = callback
        self.priority = priority
        self.conditional = conditional
        self.metadata = metadata or {}
        self.max_queue_size = max_queue_size

        self._emitter = None
        self._queue = None
        self._queue_greenlet = None

        if priority == Priority.SEQUENTIAL:
            self._queue_greenlet = gevent_spawn(self._queue_handler)

    def __del__(self):
        if self._emitter:
            self.detach()

        if self._queue_greenlet:
            self._queue_greenlet.kill()
            self._queue_greenlet = None

    def __call__(self, *args, **kwargs):
        if self._queue is not None:
            try:
                self._queue.put_nowait((args, kwargs))
            except Exception as e:  # specifically `GeventFull`
                raise e
            return

        if callable(self.conditional):
            if not self.conditional(*args, **kwargs):
                return
        return self.callback(*args, **kwargs)

    def _queue_handler(self):
        self._queue = GeventQueue(self.max_queue_size)

        while True:
            args, kwargs = self._queue.get()
            try:
                self.callback(*args, **kwargs)
            except Exception as e:
                raise e

    def attach(self, emitter):
        self._emitter = emitter

        for event in self.events:
            base = self.priority

            # Start AFTER the base (base is never used)
            if base in Priority.ALL:
                emitter._priority_offsets[base] += 1
                candidate = base + emitter._priority_offsets[base]
            else:
                candidate = base

            # Ensure global uniqueness (shift forward)
            while candidate in emitter._used_priorities:
                candidate += 1

            emitter._used_priorities.add(candidate)
            emitter.event_handlers[candidate][event] = self

            if not hasattr(self, '_resolved_priorities'):
                self._resolved_priorities = {}

            self._resolved_priorities[event] = candidate

        return self

    def detach(self, emitter=None):
        emitter = emitter or self._emitter

        for event in self.events:
            priority = self._resolved_priorities.get(event, self.priority)

            if priority in emitter.event_handlers:
                if event in emitter.event_handlers[priority]:
                    del emitter.event_handlers[priority][event]

                if not emitter.event_handlers[priority]:
                    del emitter.event_handlers[priority]

                emitter._used_priorities.discard(priority)

    def remove(self, emitter=None):
        self.detach(emitter)


class Emitter(LoggingClass):
    def __init__(self):
        self.event_handlers = defaultdict(dict)
        self._used_priorities = set()
        self._priority_offsets = defaultdict(int)
        self.pool = GeventPool()

    def emit(self, name, *args, **kwargs):
        for priority in sorted(self.event_handlers.keys()):
            listener = self.event_handlers[priority].get(name)

            if not listener:
                continue

            try:
                copied_args = tuple(
                    arg.clone() if isinstance(arg, Event) else arg
                    for arg in args
                )

                if priority == Priority.STATE:
                    self.pool.spawn(listener, *copied_args, **kwargs)
                elif priority < Priority.NONE:
                    listener(*copied_args, **kwargs)
                else:
                    gevent_spawn(listener, *copied_args, **kwargs)
            except Exception as e:
                raise Exception('{} event handler `{}` raised {}: {}'.format(
                    name,
                    getattr(listener.callback, '__name__', repr(listener.callback)),
                    e.__class__.__name__,
                    e,
                )) from e

    def on(self, *args, **kwargs):
        return EmitterSubscription(args[:-1], args[-1], **kwargs).attach(self)

    def once(self, *args, **kwargs):
        result = GeventAsyncResult()
        li = None

        def _f(e):
            result.set(e)
            li.detach()

        li = self.on(*args + (_f, ))

        return result.wait(kwargs.pop('timeout', None))

    def wait(self, *args, **kwargs):
        result = GeventAsyncResult()
        match = args[-1]

        def _f(e):
            if match(e):
                result.set(e)

        return result.wait(kwargs.pop('timeout', None))
