import inspect
from os import path as os_path

from disco.util.serializer import Serializer


class Config:
    def __init__(self, obj=None):
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
            self._parse_nested_config(obj)

    def _parse_nested_config(self, data):
        for key in dir(self):
            _attr = getattr(self, key)
            if key.startswith('__') or callable(_attr):
                continue
            if isinstance(_attr, dict):
                if any(isinstance(k, int) for k in _attr.keys()):
                    continue
                setattr(self, key, Config(obj=data[key]))
            elif inspect.isclass(_attr) and issubclass(_attr(), Config):
                setattr(self, key, _attr(obj=data[key]))

    @classmethod
    def from_file(cls, path):
        inst = cls()

        with open(path, 'r') as f:
            data = f.read()
            f.close()

        _, ext = os_path.splitext(path)
        Serializer.check_format(ext[1:])
        _data = Serializer.loads(ext[1:], data)

        inst.__dict__.update(_data)
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

    def to_dict(self, clean=True):
        result = {}
        for key, value in self.__dict__.items():
            if clean and (callable(value) or key.startswith('__')):  # Skip methods and private attributes
                continue
            if isinstance(value, Config):
                result[key] = value.to_dict(clean=clean)
            else:
                result[key] = value
        return result

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __delitem__(self, key):
        del self.__dict__[key]

    def __contains__(self, key):
        return key in self.__dict__

    def __iter__(self):
        return iter(self.__dict__)

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def items(self):
        return self.__dict__.items()