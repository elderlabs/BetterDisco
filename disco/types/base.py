from datetime import datetime as real_datetime, UTC
from functools import partial as functools_partial
from gevent import sleep as gevent_sleep
from inspect import isclass as inspect_isclass

from disco.util.chains import Chainable
from disco.util.enum import BaseEnumMeta, EnumAttr, get_enum_members
from disco.util.hashmap import HashMap
from disco.util.metaclass import with_metaclass

DATETIME_FORMATS = [
    '%Y-%m-%dT%H:%M:%S.%f',
    '%Y-%m-%dT%H:%M:%S',
]


def get_item_by_path(obj, path):
    for part in path.split('.'):
        obj = getattr(obj, part)
    return obj


class Unset:
    def __nonzero__(self):
        return False

    def __bool__(self):
        return False


UNSET = Unset()


def cached_property(method):
    method._cached_property = set()
    return method


def strict_cached_property(*args):
    def _cached_property(method):
        method._cached_property = set(args)
        return method
    return _cached_property


class ConversionError(Exception):
    def __init__(self, field, raw, e):
        super(ConversionError, self).__init__(
            'Failed to convert `{}` to `{}` - {}: {}\n{}'.format(
                field.src_name, field.true_type, e.__class__.__name__, e, raw))

        self.__cause__ = e


class Field:
    def __init__(self, value_type, alias=None, default=None, create=True, ignore_dump=None, cast=None, **kwargs):
        self.true_type = value_type
        self.src_name = alias
        self.dst_name = None
        self.ignore_dump = ignore_dump or []
        self.cast = cast
        self.metadata = kwargs

        # Only set the default value if we were given one
        if default is not None:
            self.default = default
        # Attempt to use the instances default type (e.g. from a subclass)
        elif not hasattr(self, 'default'):
            self.default = None

        self.deserializer = None

        if value_type:
            self.deserializer = self.type_to_deserializer(value_type)

            if isinstance(self.deserializer, Field) and self.default is None:
                self.default = self.deserializer.default
            elif (inspect_isclass(self.deserializer) and
                    issubclass(self.deserializer, Model) and
                    self.default is None and
                    create):
                self.default = self.deserializer

    @property
    def name(self):
        return None

    @name.setter
    def name(self, name):
        if not self.dst_name:
            self.dst_name = name

        if not self.src_name:
            self.src_name = name

    def has_default(self):
        return self.default is not None

    def try_convert(self, raw, client, **kwargs):
        try:
            return self.deserializer(raw, client, **kwargs)
        except Exception as e:
            raise ConversionError(self, raw, e)

    @staticmethod
    def type_to_deserializer(typ):
        if isinstance(typ, Field) or inspect_isclass(typ) and issubclass(typ, Model):
            return typ
        elif isinstance(typ, BaseEnumMeta):
            def _f(raw, client, **kwargs):
                return typ.get(raw)
            return _f
        elif typ is None:
            def _f(*args, **kwargs):
                return None
        else:
            def _f(raw, client, **kwargs):
                return typ(raw)
            return _f

    @staticmethod
    def serialize(value, inst=None):
        if isinstance(value, EnumAttr):
            return value.value
        if isinstance(value, real_datetime):
            return value.isoformat()
        elif isinstance(value, Model):
            return value.to_dict(ignore=(inst.ignore_dump if inst else []))
        else:
            if inst and inst.cast:
                return inst.cast(value)
            return value

    def __call__(self, raw, client, **kwargs):
        return self.try_convert(raw, client, **kwargs)


class DictField(Field):
    default = HashMap

    def __init__(self, key_type, value_type=None, **kwargs):
        super(DictField, self).__init__({}, **kwargs)
        self.true_key_type = key_type
        self.true_value_type = value_type
        self.key_de = self.type_to_deserializer(key_type)
        self.value_de = self.type_to_deserializer(value_type or key_type)

    @staticmethod
    def serialize(value, inst=None):
        return {
            Field.serialize(k): Field.serialize(v) for k, v in value.items()
            if k not in (inst.ignore_dump if inst else [])
        }

    def try_convert(self, raw, client, **kwargs):
        return HashMap({
            self.key_de(k, client): self.value_de(v, client) for k, v in raw.items()
        })


class ListField(Field):
    default = list

    @staticmethod
    def serialize(value, inst=None):
        return list(map(Field.serialize, value))

    def try_convert(self, raw, client, **kwargs):
        return [self.deserializer(i, client) for i in raw]


class AutoDictField(Field):
    default = HashMap

    def __init__(self, value_type, key, **kwargs):
        super(AutoDictField, self).__init__({}, **kwargs)
        self.value_de = self.type_to_deserializer(value_type)
        self.key = key

    def try_convert(self, raw, client, **kwargs):
        return HashMap({
            getattr(b, self.key): b for b in (self.value_de(a, client) for a in raw)
        })


def _make(typ, data, client):
    if inspect_isclass(typ) and issubclass(typ, Model):
        return typ(data, client)
    return typ(data)


def snowflake(data):
    return int(data) if data else None


def enum(typ):
    def _f(data):
        if data is None:
            return None

        for k, v in get_enum_members(typ):
            if data in (k, v):
                return EnumAttr(data, k.upper(), v, v)

        return None
    return _f


def datetime(data):
    if not data:
        return None

    if isinstance(data, int):
        return real_datetime.fromtimestamp(data, tz=UTC)

    for fmt in DATETIME_FORMATS:
        try:
            return real_datetime.strptime(data.rsplit('+', 1)[0], fmt).replace(tzinfo=UTC)
        except (ValueError, TypeError):
            continue

    raise ValueError('Failed to convert `{}` to datetime'.format(data))


def text(obj):
    if obj is None:
        return None

    return str(obj)


def str_or_int(obj):
    if obj is None:
        return None

    if str(obj).isdigit():
        return int(obj)

    try:
        return float(obj)
    except:
        return str(obj)


def with_equality(field):
    class T:
        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return getattr(self, field) == getattr(other, field)
            else:
                return getattr(self, field) == other
    return T


def with_hash(field):
    class T:
        def __hash__(self):
            return hash(getattr(self, field))
    return T


# Resolution hacks :(
Model = None
SlottedModel = None


def _get_cached_property(name, func):
    def _getattr(self):
        try:
            return getattr(self, '_' + name)
        except AttributeError:
            value = func(self)
            setattr(self, '_' + name, value)
            return value

    def _setattr(self, value):
        setattr(self, '_' + name, value)

    def _delattr(self):
        delattr(self, '_' + name)

    prop = property(_getattr, _setattr, _delattr)
    return prop


class ModelMeta(type):
    def __new__(mcs, name, parents, dct):
        fields = {}
        slots = set()

        for parent in parents:
            if Model and issubclass(parent, Model) and parent != Model:
                fields.update(parent._fields)

        for k, v in dct.items():
            if hasattr(v, '_cached_property'):
                dct[k] = _get_cached_property(k, v)
                slots.add('_' + k)

            if not isinstance(v, Field):
                continue

            v.name = k
            fields[k] = v
            slots.add(k)

        if SlottedModel and any(map(lambda k: issubclass(k, SlottedModel), parents)):
            # Merge our set of field slots with any other slots from the mro
            dct['__slots__'] = tuple(set(dct.get('__slots__', [])) | slots)

            # Remove all fields from the dict
            dct = {k: v for k, v in dct.items() if k not in dct['__slots__']}
        else:
            dct = {k: v for k, v in dct.items() if k not in fields}

        dct['_fields'] = fields
        return super(ModelMeta, mcs).__new__(mcs, name, parents, dct)


class Model(with_metaclass(ModelMeta, Chainable)):
    __slots__ = ['client']

    def __init__(self, *args, **kwargs):
        self.client = kwargs.pop('client', None)

        if len(args) == 1:
            obj = args[0]
        elif len(args) == 2:
            obj, self.client = args
        else:
            obj = kwargs
            kwargs = {}

        self.load(obj, **kwargs)
        self.validate()

    def after(self, delay):
        gevent_sleep(delay)
        return self

    def validate(self):
        pass

    @property
    def _fields(self):
        return self.__class__._fields

    def load(self, *args, **kwargs):
        return self.load_into(self, *args, **kwargs)

    @classmethod
    def load_into(cls, inst, obj, consume=False):
        for name, field in cls._fields.items():
            try:
                raw = obj[field.src_name]

                if consume and not isinstance(raw, dict):
                    del obj[field.src_name]
            except KeyError:
                raw = None

            # If the field is unset/none, and we have a default we need to set it
            if raw in (None, UNSET) and field.has_default():
                default = field.default() if callable(field.default) else field.default
                setattr(inst, field.dst_name, default)
                continue

            # Otherwise if the field is UNSET and has no default, skip conversion
            if raw is None:
                setattr(inst, field.dst_name, raw)
                continue

            value = field.try_convert(raw, inst.client, consume=consume)
            setattr(inst, field.dst_name, value)

    def inplace_update(self, other, ignored=None):
        for name in self._fields.keys():
            if ignored and name in ignored:
                continue

            if hasattr(other, name) and not getattr(other, name) is None:
                setattr(self, name, getattr(other, name))

        # Clear cached properties
        for name in dir(type(self)):
            if isinstance(getattr(type(self), name), property):
                try:
                    delattr(self, name)
                except Exception:
                    pass

    def to_dict(self, ignore=None):
        obj = {}
        for name, field in self.__class__._fields.items():
            if ignore and name in ignore:
                continue

            if field.metadata.get('private'):
                continue

            if getattr(self, name) is None:
                continue
            obj[name] = field.serialize(getattr(self, name), field)
        return obj

    @classmethod
    def create(cls, client, data, **kwargs):
        data.update(kwargs)
        inst = cls(data, client)
        return inst

    @classmethod
    def create_map(cls, client, data, *args, **kwargs):
        return list(map(functools_partial(cls.create, client, *args, **kwargs), data))

    @classmethod
    def create_hash(cls, client, key, data, **kwargs):
        return HashMap({
            get_item_by_path(item, key): item
            for item in [
                cls.create(client, item, **kwargs) for item in data]
        })

    @classmethod
    def attach(cls, it, data):
        for item in it:
            for k, v in data.items():
                try:
                    setattr(item, k, v)
                except Exception:
                    pass


class SlottedModel(Model):
    __slots__ = ['client']


class BitsetMap:
    @classmethod
    def keys(cls):
        for k, v in cls.__dict__.items():
            if k.isupper():
                yield k


class BitsetValue:
    __slots__ = ['value', 'map']

    def __init__(self, value=0):
        if isinstance(value, self.__class__):
            value = value.value

        self.value = int(value)

    def check(self, *args):
        for arg in args:
            if not (self.value & arg) == arg:
                return False
        return True

    def add(self, other):
        if isinstance(other, self.__class__):
            self.value |= other.value
        elif isinstance(other, int):
            self.value |= other
        else:
            raise TypeError('Cannot BitsetValue.add from type {}'.format(type(other)))
        return self

    def sub(self, other):
        if isinstance(other, self.__class__):
            self.value &= ~other.value
        elif isinstance(other, int):
            self.value &= ~other
        else:
            raise TypeError('Cannot BitsetValue.sub from type {}'.format(type(other)))
        return self

    def __iadd__(self, other):
        return self.add(other)

    def __isub__(self, other):
        return self.sub(other)

    def __getattribute__(self, name):
        try:
            perm_value = getattr(super(BitsetValue, self).__getattribute__('map'), name.upper())
            return (self.value & perm_value) == perm_value
        except AttributeError:
            return super(BitsetValue, self).__getattribute__(name)

    def __setattr__(self, name, value):
        try:
            perm_value = getattr(self.map, name.upper())
        except AttributeError:
            return super(BitsetValue, self).__setattr__(name, value)

        if value:
            self.value |= perm_value
        else:
            self.value &= ~perm_value

    def __int__(self):
        return self.value

    def to_dict(self):
        return {
            k: getattr(self, k) for k in tuple(self.map.keys())
        }

    def __iter__(self):
        for k, v in self.to_dict().items():
            if v:
                yield k

    def __repr__(self):
        return str(self.value)

    def __str__(self):
        if not self.value:
            return 'NONE'
        return ', '.join(i for i in self.__iter__())
