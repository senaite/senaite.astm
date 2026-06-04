# -*- coding: utf-8 -*-

import asyncio
import os

from senaite.astm import adapter_registry
from senaite.astm import logger
from senaite.astm.constants import ACK
from senaite.astm.constants import CR
from senaite.astm.constants import ENQ
from senaite.astm.constants import EOT
from senaite.astm.constants import ETB
from senaite.astm.constants import ETX
from senaite.astm.constants import LF
from senaite.astm.constants import NAK
from senaite.astm.constants import STX
from senaite.astm.exceptions import NotAccepted
from senaite.astm.interfaces import IDataHandler
from senaite.astm.utils import is_chunked_message
from senaite.astm.utils import join
from senaite.astm.utils import validate_checksum
from senaite.astm.utils import write_message
from senaite.astm.wrapper import Wrapper

TIMEOUT = 15
QUEUE = asyncio.Queue()
DEFAULT_FORMAT = "json"


class ASTMProtocol(asyncio.Protocol):
    """ASTM Protocol

    Responsible for communication and collecting complete and valid messages.

    NOTE: Every connection must be handled by an own instance of this protocol!
    """
    def __init__(self, **kwargs):
        logger.debug("ASTMProtocol:constructor")
        self.loop = asyncio.get_event_loop()
        self.queue = kwargs.get("queue", QUEUE)
        self.timeout = kwargs.get("timeout", TIMEOUT)
        self.message_format = kwargs.get("message_format", DEFAULT_FORMAT)

        self.transport = None
        self.client = None
        self.timer = None
        self.buffer = b""
        self.chunks = []
        self.messages = []
        self.in_transfer_state = False
        # Optional future, set by the client (connect) mode, that gets resolved
        # when the connection is lost so the caller can reconnect. Stays None
        # in server (listen) mode, where each connection is independent.
        self.on_connection_lost = kwargs.get("on_connection_lost", None)

    def connection_made(self, transport):
        """Called when a connection is made.
        """
        self.transport = transport
        # Remember the connected client
        self.client = self.get_client_key(transport)
        logger.debug("Connection from {!s}".format(self.client))

    def start_timer(self):
        """Start the timeout timer
        """
        # Closes the connection if no data was received after the given timeout
        self.timer = self.loop.call_later(self.timeout, self.on_timeout)

    def cancel_timer(self):
        """Cancel the timeout timer
        """
        if self.timer is None:
            return
        self.timer.cancel()

    def restart_timer(self):
        """Restart the timeout timer
        """
        self.cancel_timer()
        self.start_timer()

    def get_client_key(self, transport):
        """Return the client key for the given transport
        """
        peername = transport.get_extra_info("peername")
        return "{:s}:{:d}".format(*peername)

    def close_connection(self):
        """Cleanup and close connection
        """
        self.discard_env()
        self.transport.close()

    def discard_chunked_messages(self):
        """Flush chunked messages
        """
        self.chunks = []

    def discard_env(self):
        """Flush environment
        """
        self.chunks = []
        self.messages = []
        self.in_transfer_state = False

    def data_received(self, data):
        """Called when some data is received.

        TCP does not preserve message boundaries: a single ASTM frame can be
        split across several reads (common with serial-to-LAN gateways that
        forward a slow serial stream), and conversely several control bytes
        and/or frames can arrive in a single read. We therefore accumulate
        incoming bytes in a buffer and only dispatch *complete* tokens:
        single control bytes (ENQ/ACK/NAK/EOT), or a full frame terminated by
        <LF>.
        """
        logger.debug("-> Data received from {!s}: {!r}".format(
            self.client, data))

        # restart the timer
        # -> this ensures the next data is received within the timeout
        self.restart_timer()

        self.buffer += data
        for token in self.iter_tokens():
            # A single malformed/unexpected token must never tear down the
            # connection: log it and carry on with the next token.
            try:
                response = self.handle_data(token)
            except Exception as exc:
                logger.error("Error handling token {!r}: {!r}".format(
                    token, exc))
                continue
            if response is not None:
                logger.debug("<- Sending response: {!r}".format(response))
                self.transport.write(response)

    def iter_tokens(self):
        """Yield complete protocol tokens from the receive buffer.

        A token is either a single control byte (<ENQ>/<ACK>/<NAK>/<EOT>) or a
        whole ASTM frame: ``<STX> FN ... (<ETX>|<ETB>) C1 C2 [<CR><LF>]``. A
        frame is only emitted once its end marker *and* its two checksum bytes
        have arrived; partial frames stay in the buffer until the rest comes.
        The trailing <CR>/<LF> is optional, so this works whether the sender
        terminates frames with <CR><LF> (real instruments) or not.
        """
        while self.buffer:
            first = self.buffer[:1]
            if first in (ENQ, ACK, NAK, EOT):
                self.buffer = self.buffer[1:]
                yield first
            elif first == STX:
                # find the frame end marker (<ETX> final, or <ETB> chunked)
                markers = [i for i in (self.buffer.find(ETX),
                                       self.buffer.find(ETB)) if i != -1]
                if not markers:
                    return  # no terminator yet, wait for more data
                end = min(markers)
                # the 2 checksum bytes follow the end marker
                if len(self.buffer) < end + 3:
                    return  # checksum not fully arrived yet
                frame_end = end + 3
                # consume an optional trailing <CR> and/or <LF>
                while (self.buffer[frame_end:frame_end + 1] in (CR, LF)):
                    frame_end += 1
                frame, self.buffer = (
                    self.buffer[:frame_end], self.buffer[frame_end:])
                yield frame
            elif first in (CR, LF):
                # inter-frame whitespace (e.g. a <CR><LF> split from its
                # frame across reads): ignore silently
                self.buffer = self.buffer[1:]
            else:
                # stray/unexpected leading byte (e.g. line noise): drop it so
                # we don't stall on it, and keep scanning
                logger.warning("Discarding unexpected byte: %r", first)
                self.buffer = self.buffer[1:]

    def handle_data(self, data):
        """Process incoming data
        """
        # lookup custom multi-adapter to handle the data
        adapters = adapter_registry.getAdapters((self, data), IDataHandler)
        for name, adapter in adapters:
            if adapter and adapter.can_handle():
                return adapter.handle_data()

        response = None
        if data.startswith(ENQ):
            response = self.on_enq(data)
        elif data.startswith(ACK):
            response = self.on_ack(data)
        elif data.startswith(NAK):
            response = self.on_nak(data)
        elif data.startswith(EOT):
            response = self.on_eot(data)
        elif data.startswith(STX):
            response = self.on_message(data)
        else:
            response = self.default_handler(data)
        return response

    def default_handler(self, data):
        """Default callback
        """
        # raise ValueError("Unable to dispatch data: %r", data)
        logger.error("Unable to dispatch data: %r", data)

    def on_enq(self, data):
        """Callback when <ENQ> was received
        """
        logger.debug("on_enq: %r", data)
        if not self.in_transfer_state:
            self.in_transfer_state = True
            return ACK
        else:
            logger.error("ENQ is not expected")
            return NAK

    def on_ack(self, data):
        """Calls on <ACK> message receiving."""
        logger.debug("on_ack: %r", data)
        # We are the receiver and should never be ACKed. Ignore rather than
        # raise: an exception here would be fatal to the connection.
        logger.warning("Unexpected ACK received; ignoring")

    def on_nak(self, data):
        """Calls on <NAK> message receiving."""
        logger.debug("on_nak: %r", data)
        # As above: ignore an unexpected NAK instead of tearing down the link.
        logger.warning("Unexpected NAK received; ignoring")

    def on_eot(self, data):
        """Calls on <EOT> message receiving."""
        logger.debug("on_eot: %r", data)

        if not self.in_transfer_state:
            # Stray <EOT> outside a transfer: instruments emit these between
            # sessions (and in <EOT>/<ENQ> bursts while establishing). Ignore
            # it and stay connected -- raising here is fatal to the asyncio
            # connection and would force a needless reconnect.
            logger.warning("Received EOT outside a transfer; ignoring")
            self.discard_env()
            return

        # stop any running timer
        self.cancel_timer()

        # XXX: Seen from Yumizen H550: EOT right after ENQ.
        #      Maybe this is some kind of keepalive?
        if not self.messages:
            self.discard_env()
            return

        # Wrap the message
        wrapper = Wrapper(self.messages)

        if self.message_format == "astm":
            self.queue.put_nowait(wrapper.to_astm())
        elif self.message_format == "json":
            self.queue.put_nowait(wrapper.to_json())
        else:
            self.queue.put_nowait(wrapper.to_lis2a())

        # Store the raw message for debugging and development purposes
        self.log_message(wrapper.to_astm())

        # Drop session
        self.discard_env()

    def log_message(self, message, directory="astm_messages"):
        """Store the raw ASTM message if the folder exists in the CWD
        """
        cwd = os.getcwd()
        path = os.path.join(cwd, directory)
        if os.path.exists(path):
            write_message(message, path)

    def on_timeout(self):
        """Callback for timeout event
        """
        logger.warning("Connection for {!r} timed out after {!r}s: Closing..."
                       .format(self.client, self.timeout))
        self.close_connection()

    def on_message(self, data):
        """Callback when a message was received
        """
        logger.debug("on_message: %r", data)
        if not self.in_transfer_state:
            self.discard_chunked_messages()
            return NAK
        else:
            try:
                self.handle_message(data)
                return ACK
            except Exception as exc:
                logger.error("Error occurred on message handling. {!r}"
                             .format(exc))
                return NAK

    def handle_message(self, message):
        """Handle message data
        """

        full_message = None
        is_chunked_transfer = is_chunked_message(message)

        # message is splitted
        if is_chunked_transfer:
            self.chunks.append(message)
        # join splitted message
        elif self.chunks:
            self.chunks.append(message)
            full_message = join(self.chunks)
            self.discard_chunked_messages()
        else:
            full_message = message

        # message not yet complete
        if not full_message:
            return

        if not validate_checksum(full_message):
            raise NotAccepted("Checksum failed for '%r'" % full_message)

        self.messages.append(full_message)

    def connection_lost(self, ex):
        """Called when the connection is lost or closed.
        """
        logger.warning("Lost connection for {!s}".format(self.client))
        self.cancel_timer()
        self.discard_env()
        # Notify client (connect) mode so it can reconnect
        if self.on_connection_lost and not self.on_connection_lost.done():
            self.on_connection_lost.set_result(ex)
