from collections import defaultdict


class HashMap(dict):
    __slots__ = ()

    def iter(self):
        return iter(self)

    def items(self):
        return super(HashMap, self).items()

    def find(self, predicate):
        if not callable(predicate):
            raise TypeError('predicate must be callable')

        for obj in self.values():
            if predicate(obj):
                yield obj

    def find_one(self, predicate):
        return next(self.find(predicate), None)

    def select(self, **kwargs):
        for obj in self.values():
            for k, v in kwargs.items():
                if getattr(obj, k) != v:
                    break
                yield obj

    def select_one(self, **kwargs):
        return next(self.select(**kwargs), None)

    def filter(self, predicate):
        if not callable(predicate):
            raise TypeError('predicate must be callable')
        return filter(predicate, self.values())

    def map(self, predicate):
        if not callable(predicate):
            raise TypeError('predicate must be callable')
        return map(predicate, self.values())


class DefaultHashMap(defaultdict, HashMap):
    pass
