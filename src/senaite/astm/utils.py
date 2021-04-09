# -*- coding: utf-8 -*-

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
