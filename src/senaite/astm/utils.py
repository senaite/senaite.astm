# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime
from pathlib import Path

from senaite.astm import logger
from senaite.astm.constants import CR
from senaite.astm.constants import CRLF
from senaite.astm.constants import ETB
from senaite.astm.constants import ETX
from senaite.astm.constants import STX

try:
    from itertools import izip_longest
except ImportError:  # Python 3
    from itertools import zip_longest as izip_longest


def write_message(message, path, dateformat="%Y-%m-%d_%H:%M:%S", ext=".txt"):
    """Write ASTM Message to file
    """
    path = Path(path)
    if not path.exists():
        # ensure the directory exists
        path.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    timestamp = now.strftime(dateformat)
    filename = "{}{}".format(timestamp, ext)
    # ensure we have a bytes type message
    if isinstance(message, str):
        message = bytes(message, "utf-8")
    with open(os.path.join(path, filename), "wb") as f:
        f.write(message)


def is_chunked_message(message):
    """Checks plain message for chunked byte.
    """
    length = len(message)
    if len(message) < 5:
        return False
    if ETB not in message:
        return False
    if message.index(ETB) != length - 5:
        return False
    return True


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


def validate_checksum(message):
    """Validate the checksum of the message

    :param message: The received message (line) of the instrument
                    containing the STX at the beginning and the cecksum at
                    the end.
    :returns: True if the received message is valid or otherwise it raises
                a NotAccepted Exception.
    """
    # remove any trailing newlines at the end of the message
    message = message.rstrip(CRLF)
    # get the frame w/o STX and checksum
    frame = message[1:-2]
    # check if the checksum matches
    cs = message[-2:]
    # generate the checksum for the frame
    ccs = make_checksum(frame)
    if cs != ccs:
        logger.warn("Expected checksum '%s', got '%s'" % (cs, ccs))
        return False
    return True


def split_message(message):
    """Split the message into seqence, message and checksum

    :param message: ASTM message
    :returns: Tuple of sequence, message and checksum
    """
    # remove any trailing newlines at the end of the message
    message = message.rstrip(CRLF)
    # Remove the STX at the beginning and the checksum at the end
    frame = message[1:-2]
    # Get the checksum
    cs = message[-2:]
    # Get the sequence
    seq = frame[:1]
    if not seq.isdigit():
        raise ValueError("Invalid frame sequence: {}".format(repr(seq)))
    seq, msg = int(seq), frame[1:]
    return seq, msg, cs


def join(chunks):
    """Merges ASTM message `chunks` into single message.

    :param chunks: List of chunks as `bytes`.
    :type chunks: iterable
    """
    msg = b"1" + b"".join(c[2:-5] for c in chunks) + ETX
    return b"".join([STX, msg, make_checksum(msg), CRLF])


def split(msg, size):
    """Split `msg` into chunks with specified `size`.

    Chunk `size` value couldn't be less then 7 since each chunk goes with at
    least 7 special characters: STX, frame number, ETX or ETB, checksum and
    message terminator.

    :param msg: ASTM message.
    :type msg: bytes

    :param size: Chunk size in bytes.
    :type size: int

    :yield: `bytes`
    """
    stx, frame, msg, tail = msg[:1], msg[1:2], msg[2:-6], msg[-6:]
    assert stx == STX
    assert frame.isdigit()
    assert tail.endswith(CRLF)
    assert size is not None and size >= 7
    frame = int(frame)
    chunks = make_chunks(msg, size - 7)
    chunks, last = chunks[:-1], chunks[-1]
    idx = 0
    for idx, chunk in enumerate(chunks):
        item = b"".join([str((idx + frame) % 8).encode(), chunk, ETB])
        yield b"".join([STX, item, make_checksum(item), CRLF])
    item = b"".join([str((idx + frame + 1) % 8).encode(), last, CR, ETX])
    yield b"".join([STX, item, make_checksum(item), CRLF])


def make_chunks(s, n):
    iter_bytes = (s[i:i + 1] for i in range(len(s)))
    return [b''.join(item)
            for item in izip_longest(*[iter_bytes] * n, fillvalue=b'')]


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
