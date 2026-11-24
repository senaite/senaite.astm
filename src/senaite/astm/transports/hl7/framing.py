# -*- coding: utf-8 -*-
"""MLLP (Minimal Lower Layer Protocol) framing for HL7 messages.

The HL7 spec ships HL7 v2 payloads inside a TCP block delimited by:

    <SB> ddd ... <EB> <CR>

with:

    <SB>  = 0x0B  (ASCII vertical tab)
    <EB>  = 0x1C  (ASCII file separator)
    <CR>  = 0x0D  (ASCII carriage return)

Inside the block the HL7 message itself uses ``<CR>`` (0x0D) as the
inter-segment separator. The ``<CR>`` that terminates the *block* and
the one that terminates the *last segment* are the same byte.

Provided helpers:

- :func:`extract_messages` parses a streaming buffer, returning every
  complete MLLP block found and the unconsumed tail.
- :func:`wrap` wraps an HL7 payload in MLLP framing — used by
  acknowledgement responses.
"""

SB = b"\x0b"
EB = b"\x1c"
CR = b"\x0d"

MLLP_END = EB + CR


def wrap(payload):
    """Wrap an HL7 payload in MLLP framing.

    :param payload: HL7 message bytes. Inter-segment separators
        (``\\r``) are caller's responsibility — this function does
        not touch the payload itself.
    :returns: ``SB + payload + EB + CR``.
    """
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return SB + payload + MLLP_END


def extract_messages(buffer):
    """Parse a streaming buffer into complete MLLP blocks.

    :param buffer: bytes accumulated from the socket so far. Partial
        blocks at the tail are returned to the caller for re-use on
        the next read.

    :returns: A pair ``(messages, remainder)`` where ``messages`` is
        a list of HL7 payload bytes (one entry per complete MLLP
        block, with the SB / EB / CR markers stripped) and
        ``remainder`` is the unconsumed buffer suffix.

    Bytes that appear before the first ``SB`` are dropped — devices
    that send junk or framing leftovers shouldn't wedge the parser.
    A bare ``EB CR`` with no preceding ``SB`` is also dropped.
    """
    messages = []
    pos = 0
    while True:
        start = buffer.find(SB, pos)
        if start < 0:
            # No further SB — nothing more we can do. Drop any
            # pre-SB garbage by returning an empty remainder if
            # nothing was buffered after the last consumed message.
            remainder = buffer[pos:]
            # If there is no partial frame in flight, drop pre-SB
            # garbage entirely.
            if SB not in remainder:
                remainder = b""
            return messages, remainder

        end = buffer.find(MLLP_END, start + 1)
        if end < 0:
            # Partial frame: keep everything from SB onwards for the
            # next read.
            return messages, buffer[start:]

        payload = buffer[start + 1:end]
        messages.append(payload)
        pos = end + len(MLLP_END)
