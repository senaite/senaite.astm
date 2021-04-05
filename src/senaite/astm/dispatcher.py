# -*- coding: utf-8 -*-

from senaite.astm import logger
from senaite.astm.codecs import decode_message
from senaite.astm.mapping import Mapping
from senaite.astm.records import HeaderRecord
from senaite.astm.records import PatientRecord


class Dispatcher(object):
    """ASTM Message dispatcher
    """
    def __init__(self):
        self.dispatch = {
            'H': self.on_header,
            'P': self.on_patient,
        }
        self.wrappers = {
            'H': HeaderRecord,
            'P': PatientRecord,
        }

    def __call__(self, message):
        # sequence, records, checksum
        seq, records, cs = decode_message(message)
        for record in records:
            func = self.dispatch.get(record[0], self.on_unknown)
            wrapped = self.wrap(record)
            if isinstance(wrapped, Mapping):
                wrapped._raw_message = message
            func(wrapped)

    def wrap(self, record):
        rtype = record[0]
        if rtype in self.wrappers:
            return self.wrappers[rtype](*record)
        return record

    def _default_handler(self, record):
        logger.warn('Record remains unprocessed: %s', record)

    def on_header(self, record):
        """Header record handler."""
        self._default_handler(record)

    def on_patient(self, record):
        """Patient record handler."""
        self._default_handler(record)

    def on_unknown(self, record):
        """Fallback handler for dispatcher."""
        self._default_handler(record)
