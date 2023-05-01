# -*- coding: utf-8 -*-

import asyncio
import os

from senaite.astm import logger
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.constants import EOT
from senaite.astm.constants import NAK
from senaite.astm.constants import STX
from senaite.astm.exceptions import InvalidState
from senaite.astm.exceptions import NotAccepted
from senaite.astm.utils import is_chunked_message
from senaite.astm.utils import join
from senaite.astm.utils import make_checksum
from senaite.astm.utils import write_message

TIMEOUT = 15
QUEUE = asyncio.Queue()
DEFAULT_FORMAT = "lis2a"


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
        self.chunks = []
        self.messages = []
        self.in_transfer_state = False

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

    def data_received(self, data):
        """Called when some data is received.
        """
        logger.debug("-> Data received from {!s}: {!r}".format(
            self.client, data))
        # Closes the connection if no data was received after the given timeout
        self.restart_timer()
        # handle the data
        response = self.handle_data(data)
        if response is not None:
            logger.debug("<- Sending response: {!r}".format(response))
            self.transport.write(response)

    def handle_data(self, data):
        """Process incoming data
        """
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
        raise NotAccepted("Server should not be ACKed.")

    def on_nak(self, data):
        """Calls on <NAK> message receiving."""
        logger.debug("on_nak: %r", data)
        raise NotAccepted("Server should not be NAKed.")

    def on_eot(self, data):
        """Calls on <EOT> message receiving."""
        logger.debug("on_eot: %r", data)
        if not self.in_transfer_state:
            raise InvalidState("Server is not ready to accept EOT message.")

        # LIS-2A compliant message
        lis2a_message = b""
        # Raw ASTM message (including STX, sequence and checksum)
        astm_message = b""

        for record in self.messages:
            seq, msg, cs = self.split_message(record)
            lis2a_message += msg
            astm_message += record

        # Process either LIS-2A compliant or the raw message
        if self.message_format == "astm":
            self.queue.put_nowait(astm_message)
        else:
            self.queue.put_nowait(lis2a_message)

        # Store the raw message for debugging and development purposes
        self.log_message(astm_message)
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
        self.discard_env()
        self.transport.close()

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

        # append the raw message to the messages
        # NOTE: Conversion to LIS2-A2 format is done when EOT is received
        if self.validate_checksum(full_message):
            self.messages.append(full_message)

    def validate_checksum(self, message):
        """Validate the checksum of the message

        :param message: The received message (line) of the instrument
                        containing the STX at the beginning and the cecksum at
                        the end.
        :returns: True if the received message is valid or otherwise it raises
                  a NotAccepted Exception.
        """
        # get the frame w/o STX and checksum
        frame = message[1:-2]
        # check if the checksum matches
        cs = message[-2:]
        # generate the checksum for the frame
        ccs = make_checksum(frame)
        if cs != ccs:
            raise NotAccepted(
                "Checksum failure: expected %r, calculated %r" % (cs, ccs))
        return True

    def split_message(self, message):
        """Split the message into seqence, message and checksum
        """
        # Remove the STX at the beginning and the checksum at the end
        frame = message[1:-2]
        # Get the checksum
        cs = message[-2:]
        # Get the sequence
        seq = frame[:1]
        if not seq.isdigit():
            raise ValueError("Invalid frame sequence: {}".format(repr(seq)))
        seq, msg = int(seq), frame[1:]
        return seq, msg, cs

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

    def connection_lost(self, ex):
        """Called when the connection is lost or closed.
        """
        logger.warning("Lost connection for {!s}".format(self.client))
        self.discard_env()
        self.transport.close()
