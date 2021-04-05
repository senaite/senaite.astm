# -*- coding: utf-8 -*-

from senaite.astm import logger
from senaite.astm.codecs import decode_message


class Dispatcher(object):
    """ASTM Message dispatcher
    """
    def __init__(self):
        self.dispatch = {
            'H': self.on_header,
        }
        self.wrappers = {
        }

    def __call__(self, message):
        # sequence, records, checksum
        seq, records, cs = decode_message(message)
        for record in records:
            self.dispatch.get(record[0], self.on_unknown)(self.wrap(record))

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

    def on_unknown(self, record):
        """Fallback handler for dispatcher."""
        self._default_handler(record)
