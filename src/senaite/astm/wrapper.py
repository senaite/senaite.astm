# -*- coding: utf-8 -*-

import collections
import json

from senaite.astm.decode import decode_message
from senaite.astm.mapping import Mapping


class ASTMWrapper(object):
    """ASTM wrapper object
    """
    def __init__(self, messages, *args, **kwargs):
        self.messages = messages
        self.wrappers = {}

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
        out = collections.defaultdict(list)

        def values(obj):
            for key, field in obj._fields:
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
            data = dict(values(record))
            out[rtype].append(data)
        return json.dumps(out, indent=2)
