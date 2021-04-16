# -*- coding: utf-8 -*-

import importlib
import os
import pkgutil

from senaite.astm.constants import CR
from senaite.astm.constants import CRLF
from senaite.astm.constants import ETB
from senaite.astm.constants import ETX
from senaite.astm.constants import STX
from senaite.astm.wrapper import ASTMWrapper


def get_astm_wrappers(directories=None):
    """Return ASTM wrappers
    """
    if not isinstance(directories, (tuple, list)):
        directories = []
    cwd = os.path.dirname(__file__)
    for directory in directories:
        pkg_dir = os.path.join(cwd, directory)
        for (module_loader, name, ispkg) in pkgutil.iter_modules([pkg_dir]):
            importlib.import_module(
                'senaite.astm.instruments.' + name, __package__)
    return {
        cls.__name__.lower(): cls for cls in ASTMWrapper.__subclasses__()
    }


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


def to_frame(message):
    """Convert the message to a frame
    """
    frame_cs = message[1:-2]
    # split off checksum
    frame = frame_cs[:-2]
    if frame.endswith(CR + ETX):
        frame = frame[:-2]
    elif frame.endswith(ETB):
        frame = frame[:-1]
    # return frame w/o sequence
    return frame[1:]
