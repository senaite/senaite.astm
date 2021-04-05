# -*- coding: utf-8 -*-

from collections import Iterable
from itertools import zip_longest

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
from senaite.astm.exceptions import NotAccepted


def decode_message(message, encoding=ENCODING):
    """Decodes an ASTM message that is sent or received.

    communication routines. It should contain checksum that would be
    additionally verified.

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
        raise TypeError('bytes expected, got %r' % message)
    if not (message.startswith(STX) and message.endswith(CRLF)):
        raise NotAccepted(
            'Malformed ASTM message. Expected that it starts'
            ' with %x and followed by %x%x characters. Got: %r'
            ' ' % (ord(STX), ord(CR), ord(LF), message))
    frame_cs = message[1:-2]
    # split frame/checksum
    frame, cs = frame_cs[:-2], frame_cs[-2:]
    ccs = make_checksum(frame)
    if cs != ccs:
        raise NotAccepted(
            'Checksum failure: expected %r, calculated %r' % (cs, ccs))
    seq, records = decode_frame(frame, encoding)
    return seq, records, cs.decode()


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


def decode_frame(frame, encoding):
    """Decodes ASTM frame: list of records followed by sequence number.
    """
    if not isinstance(frame, bytes):
        raise TypeError('bytes expected, got %r' % frame)
    if frame.endswith(CR + ETX):
        frame = frame[:-2]
    elif frame.endswith(ETB):
        frame = frame[:-1]
    else:
        raise ValueError('Incomplete frame data %r.'
                         ' Expected trailing <CR><ETX> or <ETB> chars' % frame)
    seq = frame[:1].decode()
    if not seq.isdigit():
        raise ValueError('Malformed ASTM frame. Expected leading seq number %r'
                         '' % frame)
    seq, records = int(seq), frame[1:]
    return seq, [decode_record(record, encoding)
                 for record in records.split(RECORD_SEP)]


def decode_record(record, encoding):
    """Decodes ASTM record message.
    """
    fields = []
    for item in record.split(FIELD_SEP):
        if REPEAT_SEP in item:
            item = decode_repeated_component(item, encoding)
        elif COMPONENT_SEP in item:
            item = decode_component(item, encoding)
        else:
            item = item.decode(encoding)
        fields.append([None, item][bool(item)])
    return fields


def decode_component(field, encoding):
    """Decodes ASTM field component.
    """
    return [[None, item.decode(encoding)][bool(item)]
            for item in field.split(COMPONENT_SEP)]


def decode_repeated_component(component, encoding):
    """Decodes ASTM field repeated component.
    """
    return [decode_component(item, encoding)
            for item in component.split(REPEAT_SEP)]


def make_chunks(s, n):
    iter_bytes = (s[i:i + 1] for i in range(len(s)))
    return [b''.join(item)
            for item in zip_longest(*[iter_bytes] * n, fillvalue=b'')]


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
        item = b''.join([str((idx + frame) % 8).encode(), chunk, ETB])
        yield b''.join([STX, item, make_checksum(item), CRLF])
    item = b''.join([str((idx + frame + 1) % 8).encode(), last, CR, ETX])
    yield b''.join([STX, item, make_checksum(item), CRLF])


def encode(records, encoding=ENCODING, size=None, seq=1):
    """Encodes list of records into single ASTM message, also called as "packed"
    message.

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
    data = b''.join((str(seq % 8).encode(), data, CR, ETX))
    return b''.join([STX, data, make_checksum(data), CR, LF])


def encode_record(record, encoding):
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
        elif isinstance(field, str):
            _append(field.encode(encoding))
        elif isinstance(field, Iterable):
            _append(encode_component(field, encoding))
        elif field is None:
            _append(b'')
        else:
            _append(str(field).encode(encoding))
    return FIELD_SEP.join(fields)


def encode_component(component, encoding=ENCODING):
    """Encodes ASTM record field components.
    """
    items = []
    _append = items.append
    for item in component:
        if isinstance(item, bytes):
            _append(item)
        elif isinstance(item, str):
            _append(item.encode(encoding))
        elif isinstance(item, Iterable):
            return encode_repeated_component(component, encoding)
        elif item is None:
            _append(b'')
        else:
            _append(str(item).encode(encoding))

    return COMPONENT_SEP.join(items).rstrip(COMPONENT_SEP)


def encode_repeated_component(components, encoding=ENCODING):
    """Encodes repeated components.
    """
    return REPEAT_SEP.join(encode_component(item, encoding)
                           for item in components)
