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
from senaite.astm.utils import CleanupDict
from senaite.astm.utils import is_chunked_message
from senaite.astm.utils import join
from senaite.astm.utils import make_checksum
from senaite.astm.utils import write_message

TIMEOUT = 15


class ASTMProtocol(asyncio.Protocol):
    """ASTM Protocol

    Responsible for communication and collecting complete and valid messages.
    """
    def __init__(self, **kwargs):
        logger.debug("ASTMProtocol:constructor")
        self.queue = asyncio.Queue()
        self.environ = CleanupDict()
        self.loop = asyncio.get_running_loop()
        self.timeout = kwargs.get("timeout", TIMEOUT)

    def connection_made(self, transport):
        """Called when a connection is made.
        """
        self.transport = transport
        # Invoke on_timeout callback *after* the given time.
        self.timer = self.loop.call_later(self.timeout, self.on_timeout)
        logger.info("Connection from {!s}".format(self.client))

    @property
    def client(self):
        peername = self.transport.get_extra_info("peername")
        return "{:s}:{:d}".format(*peername)

    @property
    def env(self):
        """Returns the environment for the current connected client
        """
        if self.client not in self.environ:
            self.environ[self.client] = {
                "chunks": [],
                "messages": [],
                "in_transfer_state": False,
            }
        return self.environ[self.client]

    @env.setter
    def env(self, value):
        self.environ[self.client] = value

    def get_message_queue(self):
        """Queue used for message dispatching
        """
        return self.queue

    @property
    def chunks(self):
        try:
            return self.env["chunks"]
        except KeyError:
            chunks = []
            self.env["chunks"] = chunks
            return chunks

    @chunks.setter
    def chunks(self, value):
        self.env["chunks"] = value

    @property
    def messages(self):
        try:
            return self.env["messages"]
        except KeyError:
            messages = []
            self.env["messages"] = messages
            return messages

    @messages.setter
    def messages(self, value):
        self.env["messages"] = value

    @property
    def in_transfer_state(self):
        try:
            return self.env["in_transfer_state"]
        except KeyError:
            self.env["in_transfer_state"] = False
            return False

    @in_transfer_state.setter
    def in_transfer_state(self, value):
        self.env["in_transfer_state"] = bool(value)

    def data_received(self, data):
        """Called when some data is received.
        """
        self.timer.cancel()
        logger.debug("-> Data received from {!s}: {!r}".format(
            self.client, data))
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
        # raise ValueError("Unable to dispatch data: %r", data)
        logger.error("Unable to dispatch data: %r", data)

    def on_enq(self, data):
        """Calls on <ENQ> message receiving.
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
        if self.in_transfer_state:
            # LIS-2A compliant message
            lis2a_message = b""
            # Raw ASTM message (including STX, sequence and checksum)
            astm_message = b""

            for record in self.messages:
                seq, msg, cs = self.split_message(record)
                lis2a_message += msg
                astm_message += record

            # put the LIS-2A compliant message into the queue for dispatching
            self.queue.put_nowait(lis2a_message)
            # Store the raw message for debugging and development purposes
            self.write_astm_message(astm_message)
            self.discard_env()
        else:
            raise InvalidState("Server is not ready to accept EOT message.")

    def write_astm_message(self, message, directory="astm_messages"):
        """Store the ASTM message if the folder exists in the CWD
        """
        cwd = os.getcwd()
        path = os.path.join(cwd, directory)
        if os.path.exists(path):
            write_message(message, path)

    def on_timeout(self):
        """Calls when timeout event occurs. Used to limit waiting time for
        response data."""
        logger.debug("on_timeout")
        self.discard_env()
        self.transport.close()

    def on_message(self, data):
        """Calls on ASTM message receiving."""
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

        if full_message is not None:
            seq, msg, cs = self.split_message(full_message)
            self.messages.append(msg)

    def split_message(self, message):
        """Split the message into seqence, message and checksum
        """
        # Remove the STX at the beginning and the checksum at the end
        frame = message[1:-2]
        # Get the checksum
        cs = message[-2:]
        # validate the checksum
        ccs = make_checksum(frame)
        if cs != ccs:
            raise NotAccepted(
                "Checksum failure: expected %r, calculated %r" % (cs, ccs))
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
        self.environ.pop(self.client, None)

    def connection_lost(self, ex):
        """Called when the connection is lost or closed.
        """
        logger.debug("Connection lost: {!s}".format(self.client))
        self.discard_env()
        self.transport.close()
