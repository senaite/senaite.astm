# -*- coding: utf-8 -*-
"""HL7-over-MLLP transport.

A slim :class:`asyncio.Protocol` that buffers incoming TCP bytes,
extracts complete MLLP-framed HL7 messages, dispatches each via a
caller-supplied ``frame_callback``, and writes back a communication-
level :rfc:`HL7 ACK^R01` for every message it received.

The HL7 spec (HemoScreen HL7 Connectivity Protocol §3.2) mandates an
ACK before the device will send the next message, so even a
passthrough listener must respond. Parsing the inbound message
beyond the MSH header is intentionally out of scope here — the
parser layer (PR-7) takes the raw bytes and turns them into the
typed envelope.
"""

import asyncio
from datetime import datetime

from senaite.astm import logger
from senaite.astm.transports.hl7.framing import extract_messages
from senaite.astm.transports.hl7.framing import wrap

HL7_VERSION = "2.4"
SEGMENT_SEPARATOR = b"\r"
FIELD_SEPARATOR = b"|"


def _now_hl7():
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _parse_msh(message):
    """Return a minimal MSH summary used to build the ACK.

    Only the fields the ACK depends on are extracted: the encoding
    characters (MSH-2) and the message control ID (MSH-10). Any
    parse failure returns ``(b"^~\\&", b"")`` so the protocol can
    still respond with a defaulted ACK.
    """
    segments = message.split(SEGMENT_SEPARATOR)
    if not segments or not segments[0].startswith(b"MSH"):
        return b"^~\\&", b""
    msh = segments[0]
    fields = msh.split(FIELD_SEPARATOR)
    # MSH-2 is the encoding-characters string. Note that MSH-1 is the
    # field separator itself which is consumed when splitting, so the
    # encoding characters land at index 1.
    encoding = fields[1] if len(fields) > 1 else b"^~\\&"
    # MSH-10 (message control ID) sits at index 9 after the split
    # (since MSH-1 / MSH-2 are merged into the split sequence as one
    # leading element).
    control_id = fields[9] if len(fields) > 9 else b""
    return encoding, control_id


def build_ack(message, code="AA"):
    """Build a communication-level ACK^R01 for ``message``.

    :param message: The HL7 payload that just arrived (bytes,
        unwrapped from MLLP).
    :param code: ``"AA"`` for application accept, ``"AE"`` for
        application error. The HemoScreen spec also defines
        ``"CA"`` / ``"CE"`` for comm-level ACK/NAK but the device
        accepts AA/AE in practice.
    :returns: HL7 bytes (no MLLP framing — :func:`framing.wrap`
        is the caller's job).
    """
    encoding, control_id = _parse_msh(message)
    if isinstance(code, str):
        code = code.encode("ascii")
    timestamp = _now_hl7().encode("ascii")
    version = HL7_VERSION.encode("ascii")
    msh = b"|".join([
        b"MSH",
        encoding,
        b"",            # MSH-3 sending application (optional in ACK)
        b"",            # MSH-4 sending facility
        b"",            # MSH-5 receiving application
        b"",            # MSH-6 receiving facility
        timestamp,
        b"",            # MSH-8 security
        b"ACK^R01",
        control_id,
        b"",            # MSH-11 processing ID
        version,
    ])
    msa = b"|".join([b"MSA", code, control_id])
    return msh + b"\r" + msa + b"\r"


class HL7Protocol(asyncio.Protocol):
    """HL7-over-MLLP listener.

    Each TCP connection gets its own instance. Bytes are buffered
    across ``data_received`` calls and parsed greedily into MLLP
    blocks. For every complete block the protocol:

    1. invokes ``frame_callback(client, hl7_bytes)`` (must not raise);
    2. responds with an MLLP-wrapped ACK^R01.
    """

    def __init__(self, frame_callback=None):
        logger.debug("HL7Protocol:constructor")
        self.frame_callback = frame_callback
        self.transport = None
        self.client = None
        self.buffer = b""

    def connection_made(self, transport):
        self.transport = transport
        self.client = self._client_key(transport)
        logger.debug("HL7 connection from %s", self.client)

    def connection_lost(self, ex):
        logger.warning("Lost HL7 connection for %s", self.client)
        self.buffer = b""

    def data_received(self, data):
        logger.debug("-> HL7 data from %s: %d bytes", self.client, len(data))
        self.buffer += data

        messages, self.buffer = extract_messages(self.buffer)
        for message in messages:
            self._dispatch(message)
            self._respond_ack(message)

    @staticmethod
    def _client_key(transport):
        peername = transport.get_extra_info("peername")
        return "{:s}:{:d}".format(*peername)

    def _dispatch(self, message):
        if self.frame_callback is None:
            logger.debug(
                "No frame_callback registered; dropping %d-byte HL7 "
                "message", len(message))
            return
        try:
            self.frame_callback(self.client, message)
        except Exception as exc:
            logger.error(
                "HL7 frame_callback raised %r; message dropped", exc)

    def _respond_ack(self, message):
        try:
            ack = build_ack(message, code="AA")
        except Exception as exc:
            logger.error(
                "Failed to build ACK for %s: %r — closing connection",
                self.client, exc)
            self.transport.close()
            return
        framed = wrap(ack)
        logger.debug("<- HL7 ACK to %s: %d bytes", self.client, len(framed))
        self.transport.write(framed)
