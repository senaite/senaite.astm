# -*- coding: utf-8 -*-
#
# Credits to Alexander Shorin:
# https://github.com/kxepal/python-astm

from senaite.astm.compat import unicode
from senaite.astm.constants import COMPONENT_SEP
from senaite.astm.constants import CR
from senaite.astm.constants import CRLF
from senaite.astm.constants import ENCODING
from senaite.astm.constants import ETB
from senaite.astm.constants import ETX
from senaite.astm.constants import FIELD_SEP
from senaite.astm.constants import LF
from senaite.astm.constants import RECORD_SEP
from senaite.astm.constants import REPEAT_SEP
from senaite.astm.constants import STX
from senaite.astm.utils import make_checksum
from senaite.astm.utils import split

try:
    from collections import Iterable
except ImportError:  # Python 3
    from collections.abc import Iterable


# #############################################################################
# ASTM DECODE
# #############################################################################

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
    assert cs.upper() == ccs, "Checksum failure: expected %r, got %r" % (cs, ccs)
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


# #############################################################################
# ASTM ENCODE
# #############################################################################

def encode(records, encoding=ENCODING, size=None, seq=1):
    """Encodes list of records into single ASTM message

    If you need to get each record as standalone message use
    :func:`iter_encode` instead.

    If the result message is too large (greater than specified `size` if it's
    not :const:`None`), than it will be split by chunks.

    :param records: List of ASTM records.
    :type records: list

    :param encoding: Data encoding.
    :type encoding: str

    :param size: Chunk size in bytes.
    :type size: int

    :param seq: Frame start sequence number.
    :type seq: int

    :return: List of ASTM message chunks.
    :rtype: list
    """
    msg = encode_message(seq, records, encoding)
    if size is not None and len(msg) > size:
        return list(split(msg, size))
    return [msg]


def iter_encode(records, encoding=ENCODING, size=None, seq=1):
    """Encodes and emits each record as separate message.

    If the result message is too large (greater than specified `size` if it's
    not :const:`None`), than it will be split by chunks.

    :yields: ASTM message chunks.
    :rtype: str
    """
    for record in records:
        msg = encode_message(seq, [record], encoding)
        if size is not None and len(msg) > size:
            for chunk in split(msg, size):
                seq += 1
                yield chunk
        else:
            seq += 1
            yield msg


def encode_message(seq, records, encoding=ENCODING):
    """Encodes ASTM message.

    :param seq: Frame sequence number.
    :type seq: int

    :param records: List of ASTM records.
    :type records: list

    :param encoding: Data encoding.
    :type encoding: str

    :return: ASTM complete message with checksum and other control characters.
    :rtype: str
    """
    data = RECORD_SEP.join(encode_record(record, encoding)
                           for record in records)
    data = b"".join((str(seq % 8).encode(), data, CR, ETX))
    return b"".join([STX, data, make_checksum(data), CR, LF])


def encode_record(record, encoding=ENCODING):
    """Encodes single ASTM record.

    :param record: ASTM record. Each :class:`str`-typed item counted as field
                   value, one level nested :class:`list` counted as components
                   and second leveled - as repeated components.
    :type record: list

    :param encoding: Data encoding.
    :type encoding: str

    :returns: Encoded ASTM record.
    :rtype: str
    """
    fields = []
    _append = fields.append
    for field in record:
        if isinstance(field, bytes):
            _append(field)
        elif isinstance(field, unicode):
            _append(field.encode(encoding))
        elif isinstance(field, Iterable):
            _append(encode_component(field, encoding))
        elif field is None:
            _append(b"")
        else:
            _append(unicode(field).encode(encoding))
    return FIELD_SEP.join(fields)


def encode_component(component, encoding=ENCODING):
    """Encodes ASTM record field components.
    """
    items = []
    _append = items.append
    for item in component:
        if isinstance(item, bytes):
            _append(item)
        elif isinstance(item, unicode):
            _append(item.encode(encoding))
        elif isinstance(item, Iterable):
            return encode_repeated_component(component, encoding)
        elif item is None:
            _append(b"")
        else:
            _append(unicode(item).encode(encoding))

    return COMPONENT_SEP.join(items).rstrip(COMPONENT_SEP)


def encode_repeated_component(components, encoding=ENCODING):
    """Encodes repeated components.
    """
    return REPEAT_SEP.join(
        encode_component(item, encoding) for item in components)
