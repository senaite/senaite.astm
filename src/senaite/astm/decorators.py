# -*- coding: utf-8 -*-

from functools import wraps

from senaite.astm.constants import CR
from senaite.astm.constants import CRLF
from senaite.astm.constants import LF
from senaite.astm.constants import STX
from senaite.astm.exceptions import NotAccepted


def validate_message(func):
    """Validate ASTM message
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        message = args[0]
        if not isinstance(message, bytes):
            raise TypeError('Bytes expected, got {!r}'.format(message))
        if not (message.startswith(STX) and message.endswith(CRLF)):
            raise NotAccepted(
                'Malformed ASTM message. Expected that it starts'
                ' with %x and followed by %x%x characters. Got: %r'
                ' ' % (ord(STX), ord(CR), ord(LF), message))
        frame_cs = message[1:-2]
        # split frame/checksum
        frame, cs = frame_cs[:-2], frame_cs[-2:]
        from senaite.astm.utils import make_checksum
        ccs = make_checksum(frame)
        if cs != ccs:
            raise NotAccepted(
                'Checksum failure: expected %r, calculated %r' % (cs, ccs))
        return func(*args, **kwargs)
    return wrapper
