import inspect
from os import path as os_path

from disco.util.serializer import Serializer


class Config:
    def __init__(self, obj=None, parse_nested=False):
        self._parse_nested = parse_nested
        self.__dict__.update({
            k: getattr(self, k) for k in dir(self.__class__)
        })

        if hasattr(self.__class__, 'deprecated') and obj:
            for deprecated_key, replacement in self.__class__.deprecated.items():
                if deprecated_key in obj.keys():
                    warning_text = '"{0}" is deprecated.'.format(deprecated_key)
                    warning_text += ('\nReplace "{0}" with "{1}".'.format(deprecated_key, replacement)
                                     if replacement else '')

                    raise DeprecationWarning(warning_text)

        if obj:
            self.__dict__.update(obj)
            if self._parse_nested:
                self._parse_nested_config(obj)

    def _parse_nested_config(self, data):
        for key in dir(self):
            _attr = getattr(self, key)
            if key.startswith('__'):
                continue
            if isinstance(_attr, dict):
                setattr(self, key, Config(obj=data[key], parse_nested=self._parse_nested))
            elif inspect.isclass(_attr) and issubclass(_attr(), Config):
                setattr(self, key, _attr(obj=data[key], parse_nested=self._parse_nested))

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    @classmethod
    def from_file(cls, path, parse_nested=False):
        inst = cls()
        inst._parse_nested = parse_nested

        with open(path, 'r') as f:
            data = f.read()
            f.close()

        _, ext = os_path.splitext(path)
        Serializer.check_format(ext[1:])
        _data = Serializer.loads(ext[1:], data)

        inst.__dict__.update(_data)
        if parse_nested:
            inst._parse_nested_config(_data)
        return inst

    def from_prefix(self, prefix):
        prefix += '_'
        obj = {}

        for k, v in self.__dict__.items():
            if k.startswith(prefix):
                obj[k[len(prefix):]] = v

        return Config(obj)

    def update(self, other):
        if isinstance(other, Config):
            other = other.__dict__

        self.__dict__.update(other)

    def to_dict(self, clean=False):
        result = {}
        for key, value in self.__dict__.items():
            if clean and (callable(value) or key.startswith('__')):  # Skip methods and private attributes
                continue
            if isinstance(value, Config):
                result[key] = value.to_dict()
            else:
                result[key] = value
        return result
