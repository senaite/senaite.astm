# -*- coding: utf-8 -*-
"""Framing helpers for the CELL-DYN Emerald protocol.

Every line of the protocol is terminated by a carriage return
(``<CR>``, 0x0D). A frame starts with a header line holding the machine
name, followed by a frame ID line and an optional data segment::

    EMD22AL;1;310618-000034;OPERATOR<CR>     frame header
    RESULT<CR>                               frame ID
    DATE;19/02/2024<CR>                      data segment
    ...
    END_RESULT;38650<CR>                     control sum (CRC-16)

The control sum is a CRC-16 computed from the beginning of the frame
(frame header included) until the end of the line preceding the control
sum line (``<CR>`` included).

Provided helpers:

- :func:`extract_lines` parses a streaming buffer, returning every
  complete line found and the unconsumed tail.
- :func:`crc16` computes the control sum of the frame.
- :func:`build_line` builds a line to be sent to the instrument.
- :func:`is_result_frame` tells whether some bytes are a result frame.
"""

import re

# Frames are ASCII, but the SID, PID, ID (patient name), operator, user
# login and lot number fields are UTF-8 encoded (LIS specification,
# "Data Representation")
ENCODING = "utf-8"

CR = b"\r"
LF = b"\n"

# Machine names of the frame header ([MACHINE_NAME], LIS specification,
# table 4 "Instruments"). The specification of the Emerald 22 AL lists
# this one only: add the names of other models as their specification
# confirms them
MACHINE_NAMES = (b"EMD22AL",)

# Frame header: [MACHINE_NAME];W;X;Y, where W is the instrument number (2
# characters maximum), X the serial number (13 characters, including the
# '-', e.g. 312108-000014) and Y the user login
HEADER_RX = re.compile(
    rb"^(?:" + b"|".join(re.escape(name) for name in MACHINE_NAMES) +
    rb");[^;]{1,2};\d{6}-\d{6}(?:;|$)")

# Seek table of the CRC-16 computed per 4 bits, as given in the spec
CRC_TABLE = (
    0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
    0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400,
)


def crc16(data):
    """Returns the CRC-16 control sum of the given bytes

    :param data: the bytes of the frame, from the frame header until the
        end of the line preceding the control sum line (CR included)
    :returns: the control sum, as an int
    """
    crc = 0xFFFF
    for byte in bytearray(data):
        crc = CRC_TABLE[(byte ^ crc) & 15] ^ (crc >> 4)
        crc = CRC_TABLE[((byte >> 4) ^ crc) & 15] ^ (crc >> 4)
    return crc


def extract_lines(buffer):
    """Parse a streaming buffer into complete lines

    :param buffer: bytes accumulated from the socket so far
    :returns: A pair ``(lines, remainder)``, where ``lines`` is a list of
        complete lines, each one with its ``<CR>`` terminator, and
        ``remainder`` is the unconsumed buffer suffix (partial line).
        A ``<LF>`` following a ``<CR>`` in the same read is kept with
        the line, so that the bytes of the frame are kept as sent.
    """
    lines = []
    pos = 0
    while True:
        end = buffer.find(CR, pos)
        if end < 0:
            return lines, buffer[pos:]
        end += len(CR)
        if buffer[end:end + len(LF)] == LF:
            end += len(LF)
        lines.append(buffer[pos:end])
        pos = end


def build_line(*fields):
    """Returns the bytes of a line made of the given fields, separated
    by semicolons and terminated with ``<CR>``

    >>> build_line("ACK_CONNECT", "5")
    b'ACK_CONNECT;5\\r'
    """
    values = []
    for field in fields:
        if isinstance(field, bytes):
            field = field.decode(ENCODING, errors="replace")
        values.append(str(field))
    return ";".join(values).encode(ENCODING) + CR


def is_result_frame(raw):
    """Returns whether ``raw`` is a result frame, as sent by the instrument
    or exported by it to a USB drive: a frame header with a known machine
    name and a serial number, followed by the frame ID ``RESULT``. The
    control sum line is optional, as frames are captured without it

    :param raw: the bytes to check
    """
    text = raw.replace(CR + LF, CR).replace(LF, CR)
    lines = [line.strip() for line in text.split(CR) if line.strip()]
    if len(lines) < 2:
        return False
    if not HEADER_RX.match(lines[0]):
        return False
    return lines[1].upper() == b"RESULT"
