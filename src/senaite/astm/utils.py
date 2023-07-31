# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime
from pathlib import Path

from senaite.astm.codec import make_checksum
from senaite.astm.constants import CRLF
from senaite.astm.constants import ETB
from senaite.astm.constants import ETX
from senaite.astm.constants import STX


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
    if validate_checksum(message):
        # Chunked messages have no valid checksum!
        return False
    return True


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
    msg = b'1' + b''.join(c[2:-5] for c in chunks) + ETX
    return b''.join([STX, msg, make_checksum(msg), CRLF])


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
