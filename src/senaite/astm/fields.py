# -*- coding: utf-8 -*-
#
# Credits to Alexander Shorin:
# https://github.com/kxepal/python-astm

import datetime
import decimal
import inspect
import json
from itertools import islice

from senaite.astm import logger


class Field(object):
    """Base mapping field class.
    """
    def __init__(self, name=None, default=None, required=False, length=None):
        self.name = name
        self.default = default
        self.required = required
        self.length = length

    def __get__(self, instance, owner):
        if instance is None:
            return self
        value = instance._data.get(self.name)
        if value is not None:
            value = self._get_value(value)
        elif self.default is not None:
            default = self.default
            if callable(default):
                default = default()
            value = default
        return value

    def __set__(self, instance, value):
        if value is not None:
            value = self._set_value(value)
        instance._data[self.name] = value

    def _get_value(self, value):
        return value

    def _set_value(self, value):
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        else:
            value = str(value)
        if self.length is not None and len(value) > self.length:
            raise ValueError("Field %r value is too long (max %d, got %d)"
                             "" % (self.name, self.length, len(value)))
        return value


class NotUsedField(Field):
    """Mapping field for slots that the instrument may populate but
    we deliberately don't model.

    Any assigned value is silently dropped. The field used to emit a
    :exc:`UserWarning` per assignment, which drowned out real
    warnings (the cobas_c311 fixture alone produced ~78 of them per
    parse) without giving the operator anything actionable.
    """
    def __init__(self, name=None):
        super(NotUsedField, self).__init__(name)

    def _get_value(self, value):
        return None

    def _set_value(self, value):
        return None


class IntegerField(Field):
    """Mapping field for integer values.
    """
    def _get_value(self, value):
        return int(value)

    def _set_value(self, value):
        if not isinstance(value, int):
            try:
                value = self._get_value(value)
            except Exception:
                raise TypeError("Integer value expected, got %r" % value)
        return super(IntegerField, self)._set_value(value)


class DecimalField(Field):
    """Mapping field for decimal values.
    """
    def _get_value(self, value):
        return decimal.Decimal(value)

    def _set_value(self, value):
        if not isinstance(value, (int, float, decimal.Decimal)):
            raise TypeError("Decimal value expected, got %r" % value)
        return super(DecimalField, self)._set_value(value)


class TextField(Field):
    """Mapping field for string values.
    """
    def _set_value(self, value):
        if not isinstance(value, (str, bytes)):
            raise TypeError("String value expected, got %r" % value)
        return super(TextField, self)._set_value(value)


class PassthroughField(Field):
    """Field that preserves the original value shape on set.

    The default :class:`Field` stringifies any non-bytes value. That
    is lossy for instruments whose M-record slots may hold a plain
    string, a backslash-separated list, or a repeated component
    structure depending on the row type (e.g. the Horiba Yumizen
    sends HISTOGRAM, MATRIX and REAGENT records through the same
    schema). Use this for slots whose type can't be pinned down
    upfront.
    """

    def _set_value(self, value):
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return value


class EncodedStreamField(PassthroughField):
    """Field whose value is a self-describing encoded numeric stream.

    Decodes the `<DTYPE>-stream/<COMPRESSION>:<ENCODING>^<payload>`
    payload at parse time and stores the decoded list of numeric
    values. See :mod:`senaite.astm.encoded_streams` for the format.

    ASTM uses `^` as its component separator, so the codec splits
    the field into two components (`[prefix, payload]`) before it
    reaches us. We rejoin them with `^` before decoding.

    Decoding happens in `_set_value` rather than `_get_value`
    because :meth:`Mapping.to_dict` reads `obj._data[key]` directly
    and bypasses the descriptor — anything we want to surface in
    the envelope has to be the stored value, not a derived view.

    Falls back to the raw value when it does not look like an
    encoded stream (so a vendor that occasionally puts a plain text
    annotation or a repeated-component structure in the same slot
    does not break the envelope).
    """

    def _set_value(self, value):
        from senaite.astm.encoded_streams import is_encoded_stream
        from senaite.astm.encoded_streams import decode_stream
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        if (isinstance(value, list) and len(value) == 2
                and isinstance(value[0], str)
                and "-stream/" in value[0]):
            value = "{}^{}".format(value[0], value[1])
        if is_encoded_stream(value):
            return decode_stream(value)
        return value


class JSONListField(Field):
    """Converts the value into a JSON list
    """
    def _set_value(self, value):
        if not isinstance(value, list):
            value = [value]
        value = json.dumps(value)
        return super(JSONListField, self)._set_value(value)

    def _get_value(self, value, default=None):
        if default is None:
            default = []
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default


def _parse_with_formats(value, formats):
    """Try each format in order, return the first match.

    :raises ValueError: when none of the formats match.
    """
    for fmt in formats:
        try:
            return datetime.datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError("Value %r does not match any of: %s"
                     "" % (value, ", ".join(formats)))


class DateField(Field):
    """Mapping field for storing date values.

    The canonical output format is :attr:`format`. Subclasses can
    extend :attr:`parse_formats` to accept additional formats on
    input; the canonical format is always tried first.
    """
    format = "%Y%m%d"
    parse_formats = ()

    @property
    def _accepted_formats(self):
        return (self.format,) + tuple(self.parse_formats)

    def _get_value(self, value):
        return _parse_with_formats(value, self._accepted_formats)

    def _set_value(self, value):
        if isinstance(value, (str, bytes)):
            value = self._get_value(value)
        if not isinstance(value, (datetime.datetime, datetime.date)):
            raise TypeError("Datetime value expected, got %r" % value)
        return value.strftime(self.format)


class TimeField(Field):
    """Mapping field for storing times.

    The canonical output format is :attr:`format`. Subclasses can
    extend :attr:`parse_formats` to accept additional formats on
    input; the canonical format is always tried first.
    """
    format = "%H%M%S"
    parse_formats = ()

    @property
    def _accepted_formats(self):
        return (self.format,) + tuple(self.parse_formats)

    def _get_value(self, value):
        if isinstance(value, (str, bytes)):
            value = value.split(".", 1)[0]  # strip out microseconds
            parsed = _parse_with_formats(value, self._accepted_formats)
            return parsed.time()
        return value

    def _set_value(self, value):
        if isinstance(value, (str, bytes)):
            value = self._get_value(value)
        if not isinstance(value, (datetime.datetime, datetime.time)):
            raise TypeError("Datetime value expected, got %r" % value)
        if isinstance(value, datetime.datetime):
            value = value.time()
        return value.replace(microsecond=0).strftime(self.format)


class DateTimeField(Field):
    """Mapping field for storing date/time values.

    The canonical output format is :attr:`format`. Subclasses can
    extend :attr:`parse_formats` to accept additional formats on
    input; the canonical format is always tried first.
    """
    format = "%Y%m%d%H%M%S"
    parse_formats = ()

    @property
    def _accepted_formats(self):
        return (self.format,) + tuple(self.parse_formats)

    def _get_value(self, value):
        return _parse_with_formats(value, self._accepted_formats)

    def _set_value(self, value):
        if isinstance(value, (str, bytes)):
            value = self._get_value(value)
        if not isinstance(value, (datetime.datetime, datetime.date)):
            raise TypeError("Datetime value expected, got %r" % value)
        return value.strftime(self.format)


class ConstantField(Field):
    """Mapping field for constant values.

    >>> class Record(Mapping):
    ...     type = ConstantField(default="S")
    >>> rec = Record()
    >>> rec.type
    "S"
    >>> rec.type = "W"
    Traceback (most recent call last):
        ...
    ValueError: Field changing not allowed
    """
    def __init__(self, name=None, default=None, field=Field()):
        super(ConstantField, self).__init__(name, default, True, None)
        self.field = field
        self.required = True
        if self.default is None:
            raise ValueError("Constant value should be defined")

    def _get_value(self, value):
        return self.default

    def _set_value(self, value):
        value = self.field._get_value(value)
        if self.default != value:
            raise ValueError("Field changing not allowed: got %r, accepts %r"
                             "" % (value, self.default))
        return super(ConstantField, self)._set_value(value)


class SetField(Field):
    """Mapping field for a predefined set of values.

    By default, unknown values are accepted and a debug message is
    logged. A device firmware update that introduces a new status
    code should not crash parsing of every message that contains it.

    Pass ``strict=True`` to restore the legacy raise-on-unknown
    behaviour (useful for tests or for fields whose vocabulary is
    truly closed).
    """
    def __init__(self, name=None, default=None,
                 required=False, length=None,
                 values=None, field=Field(), strict=False):
        super(SetField, self).__init__(name, default, required, length)
        self.field = field
        self.values = values and set(values) or set([])
        self.strict = strict

    def _get_value(self, value):
        return self.field._get_value(value)

    def _set_value(self, value):
        value = self.field._get_value(value)
        if value not in self.values:
            if self.strict:
                raise ValueError(
                    "Unexpected value %r (%s)" % (value, self.name))
            logger.debug(
                "Field %r received unexpected value %r (allowed: %s)",
                self.name, value, sorted(self.values))
        return self.field._set_value(value)


class ComponentField(Field):
    """Mapping field for storing record component.
    """
    def __init__(self, mapping, name=None, default=None):
        self.mapping = mapping
        default = default or mapping()
        super(ComponentField, self).__init__(name, default)

    def _get_value(self, value):
        if isinstance(value, dict):
            return self.mapping(**value)
        elif isinstance(value, self.mapping):
            return value
        else:
            return self.mapping(*value)

    def _set_value(self, value):
        if isinstance(value, dict):
            return self.mapping(**value)
        elif isinstance(value, self.mapping):
            return value
        if isinstance(value, (str, bytes)):
            value = [value]
        return self.mapping(*value)


class RepeatedComponentField(Field):
    """Mapping field for storing list of record components.
    """
    def __init__(self, field, name=None, default=None):
        if isinstance(field, ComponentField):
            self.field = field
        else:
            from senaite.astm.mapping import Mapping
            assert isinstance(field, type) and issubclass(field, Mapping)
            self.field = ComponentField(field)
        default = default or []
        super(RepeatedComponentField, self).__init__(name, default)

    class Proxy(list):
        def __init__(self, seq, field):
            list.__init__(self, seq)
            self.list = seq
            self.field = field

        def _to_list(self):
            return [list(self.field._get_value(item)) for item in self.list]

        def __add__(self, other):
            obj = type(self)(self.list, self.field)
            obj.extend(other)
            return obj

        def __iadd__(self, other):
            self.extend(other)
            return self

        def __mul__(self, other):
            return type(self)(self.list * other, self.field)

        def __imul__(self, other):
            self.list *= other
            return self

        def __lt__(self, other):
            return self._to_list() < other

        def __le__(self, other):
            return self._to_list() <= other

        def __eq__(self, other):
            return self._to_list() == other

        def __ne__(self, other):
            return self._to_list() != other

        def __ge__(self, other):
            return self._to_list() >= other

        def __gt__(self, other):
            return self._to_list() > other

        def __repr__(self):
            return "<ListProxy %s %r>" % (self.list, list(self))

        def __str__(self):
            return str(self.list)

        def __unicode__(self):
            return str(self.list)

        def __delitem__(self, index):
            del self.list[index]

        def __getitem__(self, index):
            return self.field._get_value(self.list[index])

        def __setitem__(self, index, value):
            self.list[index] = self.field._set_value(value)

        def __delslice__(self, i, j):
            del self.list[i:j]

        def __getslice__(self, i, j):
            return self.__class__(self.list[i:j], self.field)

        def __setslice__(self, i, j, seq):
            self.list[i:j] = [self.field._set_value(v) for v in seq]

        def __contains__(self, value):
            for item in self:
                if item == value:
                    return True
            return False

        def __iter__(self):
            for index in range(len(self)):
                yield self[index]

        def __len__(self):
            return len(self.list)

        def __nonzero__(self):
            return bool(self.list)

        def __reduce__(self):
            return self.list.__reduce__()

        def __reduce_ex__(self, *args, **kwargs):
            return self.list.__reduce_ex__(*args, **kwargs)

        def append(self, item):
            self.list.append(self.field._set_value(item))

        def count(self, value):
            return self._to_list().count(value)

        def extend(self, other):
            self.list.extend([self.field._set_value(i) for i in other])

        def index(self, value, start=None, stop=None):
            start = start or 0
            for idx, item in enumerate(islice(self, start, stop)):
                if item == value:
                    return idx + start
            else:
                raise ValueError("%r not in list" % value)

        def insert(self, index, object):
            self.list.insert(index, self.field._set_value(object))

        def remove(self, value):
            for item in self:
                if item == value:
                    return self.list.remove(value)
            raise ValueError("Value %r not in list" % value)

        def pop(self, index=-1):
            return self.field._get_value(self.list.pop(index))

        def sort(self, cmp=None, key=None, reverse=False):
            raise NotImplementedError("In place sorting not allowed.")

    # update docstrings from list
    for name, obj in inspect.getmembers(Proxy):
        if getattr(list, name, None) is None\
           or name in ["__module__", "__doc__"]:
            continue
        if not inspect.isfunction(obj):
            continue
        obj.__doc__ = getattr(list, name).__doc__
    del name, obj

    def _get_value(self, value):
        return self.Proxy(value, self.field)

    def _set_value(self, value):
        return [self.field._set_value(item) for item in value]
