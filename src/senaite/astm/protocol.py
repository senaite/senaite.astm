# -*- coding: utf-8 -*-

import asyncio
from collections import defaultdict

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

clients = []
envs = defaultdict(dict)
TIMEOUT = 15


class ASTMProtocol(asyncio.Protocol):
    """ASTM Protocol

    Responsible for communication and collecting complete and valid messages.
    """
    def __init__(self, loop, queue, **kwargs):
        logger.debug("ASTMProtocol:constructor")
        # Invoke on_timeout callback *after* the given time.
        timeout = kwargs.get("timeout", TIMEOUT)
        self.timer = loop.call_later(timeout, self.on_timeout)
        self.queue = queue

    def connection_made(self, transport):
        """Called when a connection is made.
        """
        self.transport = transport
        peername = transport.get_extra_info('peername')
        self.ip = peername[0]
        self.client = "{:s}:{:d}".format(*peername)
        logger.debug('Connection from {}'.format(peername))
        clients.append(self)
        self.env = envs[self.ip]

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
        logger.debug('-> Data received: {!r}'.format(data))
        response = self.handle_data(data)
        if response is not None:
            logger.debug('<- Sending response: {!r}'.format(response))
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
        # raise ValueError('Unable to dispatch data: %r', data)
        logger.error('Unable to dispatch data: %r', data)

    def on_enq(self, data):
        """Calls on <ENQ> message receiving.
        """
        logger.debug('on_enq: %r', data)
        if not self.in_transfer_state:
            self.in_transfer_state = True
            return ACK
        else:
            logger.error('ENQ is not expected')
            return NAK

    def on_ack(self, data):
        """Calls on <ACK> message receiving."""
        logger.debug('on_ack: %r', data)
        raise NotAccepted('Server should not be ACKed.')

    def on_nak(self, data):
        """Calls on <NAK> message receiving."""
        logger.debug('on_nak: %r', data)
        raise NotAccepted('Server should not be NAKed.')

    def on_eot(self, data):
        """Calls on <EOT> message receiving."""
        logger.debug('on_eot: %r', data)
        if self.in_transfer_state:
            # put the records together to a message
            if self.messages:
                message = b"".join(self.messages)
                self.queue.put_nowait(message)
            self.discard_env()
        else:
            raise InvalidState('Server is not ready to accept EOT message.')

    def on_timeout(self):
        """Calls when timeout event occurs. Used to limit waiting time for
        response data."""
        logger.debug("on_timeout")
        self.discard_env()
        self.transport.close()

    def on_message(self, data):
        """Calls on ASTM message receiving."""
        logger.debug('on_message: %r', data)
        if not self.in_transfer_state:
            self.discard_chunked_messages()
            return NAK
        else:
            try:
                self.handle_message(data)
                return ACK
            except Exception as exc:
                logger.error('Error occurred on message handling. {!r}'
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

        # validate message if any
        if full_message is not None:
            self.validate_checksum(full_message)
            # remove frame number and checksum from the final message
            self.messages.append(full_message[1:-2])

    def validate_checksum(self, message):
        frame_cs = message[1:-2]
        # split frame/checksum
        frame, cs = frame_cs[:-2], frame_cs[-2:]
        ccs = make_checksum(frame)
        if cs != ccs:
            raise NotAccepted(
                'Checksum failure: expected %r, calculated %r' % (cs, ccs))
        return True

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
        logger.debug('Connection lost: {!s}'.format(self.client))
        # remove the connected client
        clients.remove(self)
