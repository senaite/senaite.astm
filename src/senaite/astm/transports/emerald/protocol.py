# -*- coding: utf-8 -*-
"""CELL-DYN Emerald transport.

A slim :class:`asyncio.Protocol` for the listener the CELL-DYN Emerald
instruments connect to. It buffers the incoming bytes, splits them in
``<CR>``-terminated lines, and drives the handshake of the protocol:

=================================== ======================================
Instrument                          Host (this protocol)
=================================== ======================================
``CONNECT;<serial>;<version>``      ``ACK_CONNECT;<version>``
``[header] RESULT_READY;<size>``    ``ACK_RESULT_READY``
``[header] RESULT ... END_RESULT``  ``ACK_RESULT;OK`` (or an error code)
``[header] CALIBRATION ... END_CALI`` ``ACK_CALI;<lot>;OK``
``DISCONNECT;<serial>``             (none)
=================================== ======================================

Complete frames (results of samples, QC, calibration, repeatability) are
checked against their control sum and dispatched via the caller-supplied
``frame_callback(client, raw_bytes)``. The callback may return an
awaitable: in that case, the frame is only acknowledged once the awaitable
is done, so that the caller can persist the frame first. This matters,
because in handshake mode the instrument does not tag as sent the results
that were not acknowledged, and proposes to send them again at next login.

Parsing the frames into an envelope is out of scope here: that is the job
of :mod:`senaite.astm.transports.emerald.parser`.
"""

import asyncio
import inspect

from senaite.astm import logger
from senaite.astm.transports.emerald.framing import build_line
from senaite.astm.transports.emerald.framing import crc16
from senaite.astm.transports.emerald.framing import extract_lines

# Format version replied to the instrument if not known yet
DEFAULT_VERSION = "9"

# Error code sent in the acknowledge when the control sum does not match
CRC_ERROR = "CRC_ERROR"

# Error code sent in the acknowledge when the frame could not be handled
HANDLING_ERROR = "ERROR"

# Upper bound of the size of a frame, to not buffer forever on a stream
# that never sends the end of the frame. Frames are a few KB.
MAX_FRAME_SIZE = 1024 * 1024


def get_fields(line):
    """Returns the fields of the line, stripped
    """
    text = line.decode("latin-1").strip("\r\n")
    return [field.strip() for field in text.split(";")]


def get_control_sum(fields):
    """Returns the control sum of an ``END_RESULT`` / ``END_CALI`` line,
    or None if not valid
    """
    try:
        return int(fields[1])
    except (IndexError, ValueError):
        return None


class EmeraldProtocol(asyncio.Protocol):
    """Listener for CELL-DYN Emerald instruments

    Each TCP connection gets its own instance.
    """

    def __init__(self, frame_callback=None):
        logger.debug("EmeraldProtocol:constructor")
        self.frame_callback = frame_callback
        self.transport = None
        self.client = None
        self.buffer = b""
        self.frame = b""
        self.serial = None
        self.version = DEFAULT_VERSION

    def connection_made(self, transport):
        self.transport = transport
        self.client = self._client_key(transport)
        logger.info("Emerald connection from %s", self.client)

    def connection_lost(self, ex):
        if self.frame or self.buffer:
            logger.warning(
                "Lost Emerald connection for %s with %d byte(s) of an "
                "incomplete frame", self.client,
                len(self.frame) + len(self.buffer))
        else:
            logger.info("Emerald connection closed for %s", self.client)
        self.buffer = b""
        self.frame = b""
        self.transport = None

    def data_received(self, data):
        logger.debug("-> Emerald data from %s: %d bytes",
                     self.client, len(data))
        self.buffer += data
        lines, self.buffer = extract_lines(self.buffer)
        for line in lines:
            try:
                self.handle_line(line)
            except Exception as exc:
                # Never tear the connection down because of a single
                # unexpected line: the instrument would keep retrying
                logger.error("Cannot handle line from %s: %r",
                             self.client, exc)
                self.frame = b""

    def handle_line(self, line):
        """Handles a complete line received from the instrument
        """
        fields = get_fields(line)
        frame_id = fields[0].upper()

        if frame_id == "CONNECT":
            # CONNECT;<serial>;<format version>
            self.serial = fields[1] if len(fields) > 2 else self.serial
            self.version = fields[-1] or self.version
            logger.info("Emerald %s connected (format version %s)",
                        self.serial, self.version)
            self.frame = b""
            self.write("ACK_CONNECT", self.version)

        elif frame_id == "DISCONNECT":
            serial = fields[1] if len(fields) > 1 else self.serial
            logger.info("Emerald %s disconnected", serial)
            self.frame = b""

        elif frame_id == "RESULT_READY":
            # [header] RESULT_READY;<result size in bytes>. The header line
            # buffered so far belongs to this request, not to the result
            self.frame = b""
            self.write("ACK_RESULT_READY")

        elif frame_id == "END_RESULT":
            frame, self.frame = self.frame, b""
            self.complete_frame(frame, get_control_sum(fields),
                                reply=("ACK_RESULT",))

        elif frame_id == "END_CALI":
            frame, self.frame = self.frame, b""
            lot = self.get_calibration_lot(frame)
            self.complete_frame(frame, get_control_sum(fields),
                                reply=("ACK_CALI", lot))

        elif frame_id == "STARTUP":
            # [header] STARTUP;<date>;<time>;<status>;<values>: single-line
            # frame with no control sum and no acknowledge
            frame, self.frame = self.frame + line, b""
            logger.info("Emerald start-up check: %s", ";".join(fields[1:4]))
            self.dispatch(frame)

        else:
            self.frame += line
            if len(self.frame) > MAX_FRAME_SIZE:
                logger.error(
                    "Emerald frame from %s exceeds %d bytes. Discarded",
                    self.client, MAX_FRAME_SIZE)
                self.frame = b""

    def get_calibration_lot(self, frame):
        """Returns the calibration lot from a calibration report frame
        """
        for line in frame.split(b"\r"):
            fields = get_fields(line)
            if fields[0].upper() == "CALIBRATION" and len(fields) > 4:
                return fields[4]
        return ""

    def complete_frame(self, frame, control_sum, reply):
        """Checks the control sum of the frame, dispatches it, and replies
        with the acknowledge: the ``reply`` fields followed by ``OK`` or by
        an error code
        """
        if control_sum is None or crc16(frame) != control_sum:
            logger.error(
                "Control sum mismatch for Emerald frame from %s "
                "(expected %s, computed %s)", self.client, control_sum,
                crc16(frame))
            self.write(*(reply + (CRC_ERROR, )))
            return

        result = self.dispatch(frame)
        if inspect.isawaitable(result):
            asyncio.ensure_future(self.reply_when_done(result, reply))
        else:
            self.reply(result, reply)

    async def reply_when_done(self, awaitable, reply):
        """Replies with the acknowledge once the awaitable is done
        """
        try:
            result = await awaitable
        except Exception as exc:
            logger.error("Emerald frame handling failed for %s: %r",
                         self.client, exc)
            result = False
        self.reply(result, reply)

    def reply(self, result, reply):
        """Replies with the acknowledge for the result of the dispatch,
        that is False when the frame could not be handled
        """
        code = HANDLING_ERROR if result is False else "OK"
        self.write(*(reply + (code, )))

    def dispatch(self, frame):
        """Hands the raw frame over to the frame callback. Returns what the
        callback returns, or False if it failed
        """
        if self.frame_callback is None:
            logger.debug("No frame_callback registered; dropping %d-byte "
                         "Emerald frame", len(frame))
            return None
        try:
            return self.frame_callback(self.client, frame)
        except Exception as exc:
            logger.error("Emerald frame_callback raised %r", exc)
            return False

    def write(self, *fields):
        """Writes a line to the instrument
        """
        if self.transport is None:
            logger.warning("Cannot reply %r to %s: connection closed",
                           fields, self.client)
            return
        line = build_line(*fields)
        logger.debug("<- Emerald reply to %s: %r", self.client, line)
        self.transport.write(line)

    @staticmethod
    def _client_key(transport):
        peername = transport.get_extra_info("peername")
        return "{:s}:{:d}".format(*peername)
