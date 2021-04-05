# -*- coding: utf-8 -*-

from itertools import zip_longest
from operator import itemgetter
from senaite.astm import logger

from senaite.astm.fields import Field


class MetaMapping(type):

    # class name, superclasses, attribute dictionary
    def __new__(mcs, name, bases, d):
        fields = []
        names = []

        def merge_fields(items):
            for name, field in items:
                if field.name is None:
                    field.name = name
                if name not in names:
                    fields.append((name, field))
                    names.append(name)
                else:
                    fields[names.index(name)] = (name, field)
        for base in bases:
            if hasattr(base, '_fields'):
                merge_fields(base._fields)

        merge_fields([(k, v) for k, v in d.items() if isinstance(v, Field)])
        if '_fields' not in d:
            d['_fields'] = fields
        else:
            merge_fields(d['_fields'])
            d['_fields'] = fields
        return super(MetaMapping, mcs).__new__(mcs, name, bases, d)


# Python 3 workaround
_MappingProxy = MetaMapping('_MappingProxy', (object,), {})


class Mapping(_MappingProxy):
    """ASTM Record Wrapper
    """

    def __init__(self, *args, **kwargs):
        # field data holder
        self._data = {}
        self._raw_data = args
        # extract the fieldnames
        fieldnames = map(itemgetter(0), self._fields)
        # NOTE: we use `zip_longest` to catch mismatching fields
        values = dict(zip_longest(fieldnames, args))
        values.update(kwargs)

        # set the values as attributes
        for attrname, field in self._fields:
            attrval = values.pop(attrname, None)
            if attrval is None:
                setattr(self, attrname, getattr(self, attrname))
            else:
                setattr(self, attrname, attrval)

        # remove empty items in case that not the whole schema is defined
        unset = values.pop(None, None)
        if unset:
            logger.debug('Unset field value found: {!r}'.format(unset))

        if values:
            raise ValueError('Unexpected kwargs found: %r' % values)

    @classmethod
    def build(cls, *a):
        fields = []
        newcls = type('Generic' + cls.__name__, (cls,), {})
        for field in a:
            if field.name is None:
                raise ValueError('Name is required for ordered fields.')
            setattr(newcls, field.name, field)
            fields.append((field.name, field))
        newcls._fields = fields
        return newcls

    def __getitem__(self, key):
        return self.values()[key]

    def __setitem__(self, key, value):
        setattr(self, self._fields[key][0], value)

    def __delitem__(self, key):
        self._data[self._fields[key][0]] = None

    def __iter__(self):
        return iter(self.values())

    def __contains__(self, item):
        return item in self.values()

    def __len__(self):
        return len(self._data)

    def __eq__(self, other):
        if len(self) != len(other):
            return False
        for key, value in zip(self.keys(), other):
            if getattr(self, key) != value:
                return False
        return True

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join('%s=%r' % (key, value)
                                     for key, value in self.items()))

    def keys(self):
        return [key for key, field in self._fields]

    def values(self):
        return [getattr(self, key) for key in self.keys()]

    def items(self):
        return [(key, getattr(self, key)) for key, field in self._fields]

    def to_astm(self):
        def values(obj):
            for key, field in obj._fields:
                value = obj._data[key]
                if isinstance(value, Mapping):
                    yield list(values(value))
                elif isinstance(value, list):
                    stack = []
                    for item in value:
                        if isinstance(item, Mapping):
                            stack.append(list(values(item)))
                        else:
                            stack.append(item)
                    yield stack
                elif value is None and field.required:
                    raise ValueError('Field %r value should not be None' % key)
                else:
                    yield value
        return list(values(self))


class Record(Mapping):
    """ASTM record mapping class.
    """


class Component(Mapping):
    """ASTM component mapping class.
    """
