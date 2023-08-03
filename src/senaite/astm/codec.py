# -*- coding: utf-8 -*-
#
# Credits to Alexander Shorin:
# https://github.com/kxepal/python-astm/blob/master/astm/codec.py

from senaite.astm.constants import COMPONENT_SEP
from senaite.astm.constants import CR
from senaite.astm.constants import CRLF
from senaite.astm.constants import ENCODING
from senaite.astm.constants import ETB
from senaite.astm.constants import ETX
from senaite.astm.constants import FIELD_SEP
from senaite.astm.constants import RECORD_SEP
from senaite.astm.constants import REPEAT_SEP
from senaite.astm.constants import STX


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


def decode(data, encoding=ENCODING):
    """Common ASTM decoding function that tries to guess which kind of data it
    handles.

    If `data` starts with STX character (``0x02``) than probably it is
    full ASTM message with checksum and other system characters.

    If `data` starts with digit character (``0-9``) than probably it is
    frame of records leading by his sequence number. No checksum is expected
    in this case.

    Otherwise it counts `data` as regular record structure.

    Note, that `data` should be bytes, not unicode string even if you know his
    `encoding`.

    :param data: ASTM data object.
    :type data: bytes

    :param encoding: Data encoding.
    :type encoding: str

    :return: List of ASTM records with unicode data.
    :rtype: list
    """
    if not isinstance(data, bytes):
        raise TypeError("bytes expected, got %r" % data)
    if data.startswith(STX):  # may be decode message \x02...\x03CS\r\n
        seq, records, cs = decode_message(data, encoding)
        return records
    byte = data[:1].decode()
    if byte.isdigit():
        seq, records = decode_frame(data, encoding)
        return records
    return [decode_record(data, encoding)]


def decode_message(message, encoding=ENCODING):
    """Decodes complete ASTM message that is sent or received due
    communication routines.

    :param message: ASTM message.
    :type message: bytes

    :param encoding: Data encoding.
    :type encoding: str

    :returns: Tuple of three elements:

        * :class:`int` frame sequence number.
        * :class:`list` of records with unicode data.
        * :class:`bytes` checksum.

    :raises:
        * :exc:`ValueError` if ASTM message is malformed.
        * :exc:`AssertionError` if checksum verification fails.
    """
    if not isinstance(message, bytes):
        raise TypeError("bytes expected, got %r" % message)
    if not message.startswith(STX):
        raise ValueError("ASTM message does not start with STX")
    # remove STX and CRLF
    frame_cs = message.lstrip(STX).rstrip(CRLF)
    # split checksum
    frame, cs = frame_cs[:-2], frame_cs[-2:]
    # validate the checksum
    ccs = make_checksum(frame)
    assert cs == ccs, "Checksum failure: expected %r, got %r" % (cs, ccs)
    seq, records = decode_frame(frame, encoding)
    return seq, records, cs.decode()


def decode_frame(frame, encoding=ENCODING):
    """Decodes ASTM frame: list of records followed by sequence number.
    """
    if not isinstance(frame, bytes):
        raise TypeError("bytes expected, got %r" % frame)
    if frame.endswith(CR + ETX):
        frame = frame[:-2]
    elif frame.endswith(ETB):
        frame = frame[:-1]
    else:
        raise ValueError("Incomplete frame data %r. "
                         "Expected trailing <CR><ETX> or <ETB> chars" % frame)
    seq = frame[:1].decode()
    if not seq.isdigit():
        raise ValueError("Malformed ASTM frame. Expected leading seq number %r"
                         "" % frame)
    seq, records = int(seq), frame[1:]
    return seq, [decode_record(record, encoding)
                 for record in records.split(RECORD_SEP)]


def decode_record(record, encoding=ENCODING):
    """Decodes ASTM record message
    """
    fields = []
    for item in record.split(FIELD_SEP):
        if REPEAT_SEP in item:
            item = decode_repeated_component(item, encoding)
        elif COMPONENT_SEP in item:
            item = decode_component(item, encoding)
        else:
            item = item.decode(encoding)
        # default `None` if item evalualtes to `False`
        fields.append([None, item][bool(item)])
    return fields


def decode_component(field, encoding=ENCODING):
    """Decodes ASTM field component
    """
    return [[None, item.decode(encoding)][bool(item)]
            for item in field.split(COMPONENT_SEP)]


def decode_repeated_component(component, encoding=ENCODING):
    """Decodes ASTM field repeated component
    """
    return [decode_component(item, encoding)
            for item in component.split(REPEAT_SEP)]
