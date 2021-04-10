# -*- coding: utf-8 -*-

import json
import copy

from senaite.astm.decode import decode_message
from senaite.astm.mapping import Mapping
from senaite.astm.fields import NotUsedField


class ASTMWrapper(object):
    """ASTM wrapper object
    """
    def __init__(self, messages, *args, **kwargs):
        self.messages = messages
        self.wrappers = {}
        self.skip_keys = []
        self.json_format = {}

    @property
    def records(self):
        out = []
        for message in self.messages:
            # sequence, records, checksum
            seq, records, cs = decode_message(message)
            for record in records:
                out.append(self.wrap(record))
        return out

    def wrap(self, record):
        rtype = record[0]
        if rtype in self.wrappers:
            return self.wrappers[rtype](*record)
        return record

    def to_json(self):
        out = copy.deepcopy(self.json_format)

        def values(obj):
            for key, field in obj._fields:
                if isinstance(field, NotUsedField):
                    continue
                if key in self.skip_keys:
                    continue
                value = obj._data[key]
                if isinstance(value, Mapping):
                    yield (key, list(values(value)))
                elif isinstance(value, list):
                    stack = []
                    for item in value:
                        if isinstance(item, Mapping):
                            stack.append(list(values(item)))
                        else:
                            stack.append(item)
                    yield (key, stack)
                elif value is None and field.required:
                    raise ValueError('Field %r value should not be None' % key)
                else:
                    yield (key, value)

        for record in self.records:
            rtype = record.type
            jtype = out.get(rtype)
            if jtype is None:
                continue
            data = dict(values(record))
            if isinstance(jtype, (list, tuple)):
                out[rtype].append(data)
            else:
                out[rtype] = data

        return json.dumps(out, indent=2)
