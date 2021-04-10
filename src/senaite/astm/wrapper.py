# -*- coding: utf-8 -*-

from senaite.astm.decode import decode_message


class ASTMWrapper(object):
    """ASTM wrapper object
    """
    def __init__(self, messages, *args, **kwargs):
        self.messages = messages
        self.wrappers = {}

    def get_records(self):
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
        out = {}
        return out
