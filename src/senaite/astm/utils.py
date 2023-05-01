# -*- coding: utf-8 -*-

import time

from senaite.astm.constants import CRLF
from senaite.astm.constants import ETB
from senaite.astm.constants import ETX
from senaite.astm.constants import STX


def is_chunked_message(message):
    """Checks plain message for chunked byte.
    """
    length = len(message)
    if len(message) < 5:
        return False
    if ETB not in message:
        return False
    return message.index(ETB) == length - 5


def join(chunks):
    """Merges ASTM message `chunks` into single message.

    :param chunks: List of chunks as `bytes`.
    :type chunks: iterable
    """
    msg = b'1' + b''.join(c[2:-5] for c in chunks) + ETX
    return b''.join([STX, msg, make_checksum(msg), CRLF])


def make_checksum(message):
    """Calculates checksum for specified message.

    :param message: ASTM message.
    :type message: bytes

    :returns: Checksum value that is actually byte sized integer in hex base
    :rtype: bytes
    """
    if not isinstance(message[0], int):
        message = map(ord, message)
    return hex(sum(message) & 0xFF)[2:].upper().zfill(2).encode()


class CleanupDict(dict):
    """A dict that automatically cleans up items that haven't been
    accessed in a given timespan on *set*.
    """

    cleanup_period = 60 * 5  # 5 minutes

    def __init__(self, cleanup_period=None):
        super(CleanupDict, self).__init__()
        self._last_access = {}
        if cleanup_period is not None:
            self.cleanup_period = cleanup_period

    def __getitem__(self, key):
        value = super(CleanupDict, self).__getitem__(key)
        self._last_access[key] = time.time()
        return value

    def __setitem__(self, key, value):
        super(CleanupDict, self).__setitem__(key, value)
        self._last_access[key] = time.time()
        self._cleanup()

    def _cleanup(self):
        now = time.time()
        okay = now - self.cleanup_period
        for key, timestamp in list(self._last_access.items()):
            if timestamp < okay:
                del self._last_access[key]
                super(CleanupDict, self).__delitem__(key)
