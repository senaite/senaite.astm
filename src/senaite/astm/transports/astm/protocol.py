# -*- coding: utf-8 -*-
"""ASTM-over-TCP transport.

A slim :class:`asyncio.Protocol` that owns only the framing state
machine: ENQ/ACK/NAK/STX/EOT handling, chunked-frame reassembly,
checksum validation, and the per-connection inactivity timer. Once an
EOT closes a session, the collected frames are handed to a caller-
supplied ``frame_callback``. Wrapping into an :class:`Envelope`,
serialisation, queueing, disk capture and LIMS push all live outside
this transport (see :mod:`senaite.astm.cli.astm_server` and
:mod:`senaite.astm.core.pipeline`).
"""

import asyncio

from senaite.astm import logger
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.constants import EOT
from senaite.astm.constants import ETB
from senaite.astm.constants import ETX
from senaite.astm.constants import NAK
from senaite.astm.constants import STX
from senaite.astm.core.instrument import find_raw_data_handler
from senaite.astm.exceptions import InvalidState
from senaite.astm.exceptions import NotAccepted
from senaite.astm.transports.astm.framing import is_chunked_message
from senaite.astm.transports.astm.framing import join
from senaite.astm.transports.astm.framing import validate_checksum

TIMEOUT = 15


class ASTMProtocol(asyncio.Protocol):
    """ASTM transport protocol.

    Each TCP connection gets its own instance. Complete sessions
    (ENQ ... EOT) are handed off via ``frame_callback(client, frames)``
    where ``frames`` is the list of validated, reassembled frame
    bytes in arrival order.
    """

    def __init__(self, frame_callback=None, timeout=TIMEOUT,
                 stats=None):
        """
        :param stats: Optional :class:`senaite.astm.admin.AdminStats`
            counter bag. When supplied, the protocol calls
            `stats.session_opened()` on connect and
            `stats.session_closed()` on disconnect. None is the
            documented default — the protocol works standalone in
            tests that don't care about admin metrics.
        """
        logger.debug("ASTMProtocol:constructor")
        self.frame_callback = frame_callback
        self.timeout = timeout
        self.stats = stats

        self.loop = None
        self.transport = None
        self.client = None
        self.timer = None
        self.chunks = []
        self.messages = []
        self.in_transfer_state = False
        # Per-connection input buffer. TCP delivers byte streams,
        # not framed messages, so a single ASTM frame can arrive
        # split across multiple `data_received` calls (typically
        # the large M / R frames). Accumulating into a buffer and
        # slicing complete units off the front avoids the previous
        # behaviour where a partial frame would be NAKed and the
        # continuation bytes would be dropped as un-dispatchable.
        self.buffer = b""

    # ------------------------------------------------------------------
    # asyncio.Protocol callbacks
    # ------------------------------------------------------------------

    def connection_made(self, transport):
        # In production the server is always running inside an
        # asyncio loop, so ``get_running_loop()`` is the right
        # call and avoids the ``DeprecationWarning`` emitted by
        # ``get_event_loop()`` on Python 3.12+. Synchronous unit
        # tests instantiate the protocol outside a loop; fall back
        # to a fresh loop so they keep working.
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
        self.transport = transport
        self.client = self.get_client_key(transport)
        logger.debug("Connection from {!s}".format(self.client))
        if self.stats is not None:
            self.stats.session_opened()

    def connection_lost(self, ex):
        # Distinguish "client closed without sending data" (typical
        # TCP health probe from Zabbix / load balancer / k8s liveness
        # check) from "an in-flight session was cut mid-message". The
        # former is routine noise; the latter is operationally
        # interesting and stays at WARNING.
        if self._session_was_empty():
            logger.debug(
                "Connection closed without data from %s", self.client)
        else:
            logger.warning(
                "Lost connection for %s", self.client)
        if self.stats is not None:
            self.stats.session_closed()
        self.close_connection()

    def _session_was_empty(self):
        """True when nothing was received between connect and close."""
        return (not self.in_transfer_state
                and not self.chunks
                and not self.messages)

    def data_received(self, data):
        logger.debug("-> Data received from {!s}: {!r}".format(
            self.client, data))
        self.restart_timer()
        self.buffer += data

        # Non-ASTM wire formats (mini_vidas, spotchem) ship a
        # single packet that doesn't follow ENQ/STX/EOT framing.
        # Their `raw_data_regex` matches the full payload, so we
        # only invoke the raw handler once the buffer holds a
        # complete match. Until then the bytes stay buffered and
        # this branch returns; a later `data_received` retries.
        if not self.in_transfer_state:
            instrument = find_raw_data_handler(self.buffer)
            if instrument is not None:
                payload = self.buffer
                self.buffer = b""
                response = instrument.handle_raw_data(self, payload)
                if response is not None:
                    logger.debug(
                        "<- Sending response: {!r}".format(response))
                    self.transport.write(response)
                return

        # ASTM framing: peel one logical unit (single-byte signal
        # or a complete STX..ETX/ETB+checksum frame) off the front
        # of the buffer at a time, dispatch it, and write whatever
        # response the dispatch produced. Stop when the buffer no
        # longer holds a complete unit so the remaining bytes can
        # be joined with the next `data_received` payload.
        while True:
            unit = self._pop_one_unit()
            if unit is None:
                return
            response = self.handle_data(unit)
            if response is not None:
                logger.debug(
                    "<- Sending response: {!r}".format(response))
                self.transport.write(response)

    def _pop_one_unit(self):
        """Slice one ASTM unit off the front of :attr:`buffer`.

        Returns the unit bytes (single-byte signal or complete
        frame) on success. Returns None when the buffer is empty
        or holds a partial frame whose terminator/checksum has
        not arrived yet.

        Leading garbage (bytes that are not a known signal byte
        and not an STX) is skipped one byte at a time with a
        warning; this matches the previous behaviour where the
        same bytes would have hit `default_handler` and been
        logged at ERROR.
        """
        if not self.buffer:
            return None

        first = self.buffer[:1]
        if first in (ENQ, ACK, NAK, EOT):
            self.buffer = self.buffer[1:]
            return first

        if first != STX:
            logger.warning(
                "Skipping unexpected byte %r in buffer", first)
            self.buffer = self.buffer[1:]
            return self._pop_one_unit()

        # STX-prefixed frame: locate the first ETX or ETB and
        # require the two checksum bytes that follow.
        etx = self.buffer.find(ETX, 1)
        etb = self.buffer.find(ETB, 1)
        candidates = [c for c in (etx, etb) if c >= 0]
        if not candidates:
            return None
        terminator = min(candidates)
        end = terminator + 3  # +1 for terminator, +2 for checksum
        if len(self.buffer) < end:
            return None

        # Many instruments wrap frames in `\r\n` for serial-line
        # parity with classic ASTM. Include those trailing bytes
        # in the returned frame so downstream helpers that key off
        # the wire shape (notably `is_chunked_message`, which
        # expects the ETB to sit at `len(frame) - 5`) keep working.
        tail = end
        if self.buffer[tail:tail + 1] == b"\r":
            tail += 1
        if self.buffer[tail:tail + 1] == b"\n":
            tail += 1
        frame = self.buffer[:tail]
        self.buffer = self.buffer[tail:]
        return frame

    # ------------------------------------------------------------------
    # Timer management
    # ------------------------------------------------------------------

    def start_timer(self):
        self.timer = self.loop.call_later(self.timeout, self.on_timeout)

    def cancel_timer(self):
        if self.timer is None:
            return
        self.timer.cancel()

    def restart_timer(self):
        self.cancel_timer()
        self.start_timer()

    def on_timeout(self):
        logger.warning(
            "Connection for {!r} timed out after {!r}s: Closing..."
            .format(self.client, self.timeout))
        self.close_connection()

    # ------------------------------------------------------------------
    # Connection / session lifecycle
    # ------------------------------------------------------------------

    def get_client_key(self, transport):
        peername = transport.get_extra_info("peername")
        return "{:s}:{:d}".format(*peername)

    def close_connection(self):
        self.reset_session_state()
        if self.transport is not None:
            self.transport.close()

    def discard_chunked_messages(self):
        self.chunks = []

    def reset_session_state(self):
        """Drop any partial session state so the protocol is ready
        for the next ENQ/STX/EOT cycle."""
        self.chunks = []
        self.messages = []
        self.in_transfer_state = False
        self.buffer = b""

    # ------------------------------------------------------------------
    # Byte-level dispatch
    # ------------------------------------------------------------------

    def handle_data(self, data):
        # First chance: a registered instrument may own this raw,
        # non-ASTM packet (mini_vidas, spotchem_el).
        instrument = find_raw_data_handler(data)
        if instrument is not None:
            return instrument.handle_raw_data(self, data)

        if data.startswith(ENQ):
            return self.on_enq(data)
        if data.startswith(ACK):
            return self.on_ack(data)
        if data.startswith(NAK):
            return self.on_nak(data)
        if data.startswith(EOT):
            return self.on_eot(data)
        if data.startswith(STX):
            return self.on_message(data)
        return self.default_handler(data)

    def default_handler(self, data):
        logger.error("Unable to dispatch data: %r", data)

    def on_enq(self, data):
        logger.debug("on_enq: %r", data)
        if self.in_transfer_state:
            logger.error("ENQ is not expected")
            return NAK
        self.in_transfer_state = True
        return ACK

    def on_ack(self, data):
        logger.debug("on_ack: %r", data)
        raise NotAccepted("Server should not be ACKed.")

    def on_nak(self, data):
        logger.debug("on_nak: %r", data)
        raise NotAccepted("Server should not be NAKed.")

    def on_eot(self, data):
        logger.debug("on_eot: %r", data)

        if not self.in_transfer_state:
            self.close_connection()
            raise InvalidState("Server is not ready to accept EOT message.")

        self.cancel_timer()

        # XXX: Seen from Yumizen H550: EOT right after ENQ.
        #      Maybe this is some kind of keepalive?
        if not self.messages:
            self.reset_session_state()
            return

        frames = list(self.messages)
        self.dispatch_frames(frames)
        self.reset_session_state()

    def on_message(self, data):
        logger.debug("on_message: %r", data)
        if not self.in_transfer_state:
            self.discard_chunked_messages()
            return NAK
        try:
            self.handle_message(data)
            return ACK
        except Exception as exc:
            logger.error("Error occurred on message handling. {!r}"
                         .format(exc))
            return NAK

    def handle_message(self, message):
        full_message = None
        is_chunked_transfer = is_chunked_message(message)

        if is_chunked_transfer:
            self.chunks.append(message)
        elif self.chunks:
            self.chunks.append(message)
            full_message = join(self.chunks)
            self.discard_chunked_messages()
        else:
            full_message = message

        if not full_message:
            return

        if not validate_checksum(full_message):
            raise NotAccepted("Checksum failed for '%r'" % full_message)

        self.messages.append(full_message)

    # ------------------------------------------------------------------
    # Frame dispatch
    # ------------------------------------------------------------------

    def dispatch_frames(self, frames):
        """Hand the completed session's frames to the registered
        callback. Errors in the callback do not affect the transport.
        """
        if self.frame_callback is None:
            logger.debug("No frame_callback registered; dropping %d frames",
                         len(frames))
            return
        # Bare-Exception catch on purpose: the frame_callback is
        # caller-supplied, so any error there must not propagate
        # up to the asyncio Protocol layer and tear the transport
        # down for unrelated future sessions. We log type + repr
        # so the operator can tell apart a programming error from
        # a downstream LIMS / disk error.
        try:
            self.frame_callback(self.client, frames)
        except Exception as exc:
            logger.error(
                "frame_callback raised %s: %r; frames dropped",
                type(exc).__name__, exc)
