import six
import gevent
import inspect
import functools

from datetime import datetime as real_datetime

from disco.util.chains import Chainable
from disco.util.hashmap import HashMap
from disco.util.enum import get_enum_members

DATETIME_FORMATS = [
    '%Y-%m-%dT%H:%M:%S.%f',
    '%Y-%m-%dT%H:%M:%S',
]


def get_item_by_path(obj, path):
    for part in path.split('.'):
        obj = getattr(obj, part)
    return obj


class Unset(object):
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
            'Failed to convert `{}` (`{}`) to {}: {}'.format(
                str(raw)[:144], field.src_name, field.true_type, e))

        if six.PY3:
            self.__cause__ = e


class Field(object):
    def __init__(self, value_type, alias=None, default=UNSET, create=True, ignore_dump=None, cast=None, **kwargs):
        # TODO: fix default bullshit
        self.true_type = value_type
        self.src_name = alias
        self.dst_name = None
        self.ignore_dump = ignore_dump or []
        self.cast = cast
        self.metadata = kwargs

        # Only set the default value if we where given one
        if default is not UNSET:
            self.default = default
        # Attempt to use the instances default type (e.g. from a subclass)
        elif not hasattr(self, 'default'):
            self.default = UNSET

        self.deserializer = None

        if value_type:
            self.deserializer = self.type_to_deserializer(value_type)

            if isinstance(self.deserializer, Field) and self.default is UNSET:
                self.default = self.deserializer.default
            elif (inspect.isclass(self.deserializer) and
                    issubclass(self.deserializer, Model) and
                    self.default is UNSET and
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
        return self.default is not UNSET

    def try_convert(self, raw, client, **kwargs):
        try:
            return self.deserializer(raw, client, **kwargs)
        except Exception as e:
            six.reraise(ConversionError, ConversionError(self, raw, e))

    @staticmethod
    def type_to_deserializer(typ):
        if isinstance(typ, Field) or inspect.isclass(typ) and issubclass(typ, Model):
            return typ
        # elif isinstance(typ, BaseEnumMeta):
        #    def _f(raw, client, **kwargs):
        #        return typ.get(raw)
        #    return _f
        elif typ is None:
            def _f(*args, **kwargs):
                return None
        else:
            def _f(raw, client, **kwargs):
                return typ(raw)
            return _f

    @staticmethod
    def serialize(value, inst=None):
        if isinstance(value, Model):
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
            Field.serialize(k): Field.serialize(v) for k, v in six.iteritems(value)
            if k not in (inst.ignore_dump if inst else [])
        }

    def try_convert(self, raw, client, **kwargs):
        return HashMap({
            self.key_de(k, client): self.value_de(v, client) for k, v in six.iteritems(raw)
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
    if inspect.isclass(typ) and issubclass(typ, Model):
        return typ(data, client)
    return typ(data)


def snowflake(data):
    return int(data) if data else None


def enum(typ):
    def _f(data):
        if data is None:
            return None

        for k, v in get_enum_members(typ):
            if isinstance(data, six.string_types) and k == data.upper():
                return v
            elif k == data or v == data:
                return v

        return None
    return _f


def datetime(data):
    if not data:
        return None

    if isinstance(data, int):
        return real_datetime.utcfromtimestamp(data)

    for fmt in DATETIME_FORMATS:
        try:
            return real_datetime.strptime(data.rsplit('+', 1)[0], fmt)
        except (ValueError, TypeError):
            continue

    raise ValueError('Failed to convert `{}` to datetime'.format(data))


def text(obj):
    if obj is None:
        return None

    if six.PY2:
        if isinstance(obj, str):
            return obj.decode('utf-8')
    return six.text_type(obj)


def with_equality(field):
    class T(object):
        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return getattr(self, field) == getattr(other, field)
            else:
                return getattr(self, field) == other
    return T


def with_hash(field):
    class T(object):
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
        setattr(self, '_' + name)

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

        for k, v in six.iteritems(dct):
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
            dct = {k: v for k, v in six.iteritems(dct) if k not in dct['__slots__']}
        else:
            dct = {k: v for k, v in six.iteritems(dct) if k not in fields}

        dct['_fields'] = fields
        return super(ModelMeta, mcs).__new__(mcs, name, parents, dct)


class Model(six.with_metaclass(ModelMeta, Chainable)):
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
        gevent.sleep(delay)
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
        for name, field in six.iteritems(cls._fields):
            try:
                raw = obj[field.src_name]

                if consume and not isinstance(raw, dict):
                    del obj[field.src_name]
            except KeyError:
                raw = UNSET

            # If the field is unset/none, and we have a default we need to set it
            if raw in (None, UNSET) and field.has_default():
                default = field.default() if callable(field.default) else field.default
                setattr(inst, field.dst_name, default)
                continue

            # Otherwise if the field is UNSET and has no default, skip conversion
            if raw is UNSET:
                setattr(inst, field.dst_name, raw)
                continue

            value = field.try_convert(raw, inst.client, consume=consume)
            setattr(inst, field.dst_name, value)

    def inplace_update(self, other, ignored=None):
        for name in six.iterkeys(self._fields):
            if ignored and name in ignored:
                continue

            if hasattr(other, name) and not getattr(other, name) is UNSET:
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
        for name, field in six.iteritems(self.__class__._fields):
            if ignore and name in ignore:
                continue

            if getattr(self, name) is UNSET:
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
        return list(map(functools.partial(cls.create, client, *args, **kwargs), data))

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
            for k, v in six.iteritems(data):
                try:
                    setattr(item, k, v)
                except Exception:
                    pass


class SlottedModel(Model):
    __slots__ = ['client']
