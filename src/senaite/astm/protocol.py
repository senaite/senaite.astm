# -*- coding: utf-8 -*-

import asyncio
from collections import defaultdict
from datetime import datetime

from senaite.astm import logger
from senaite.astm.codecs import is_chunked_message
from senaite.astm.codecs import join
from senaite.astm.codecs import make_checksum
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.constants import EOT
from senaite.astm.constants import NAK
from senaite.astm.constants import STX
from senaite.astm.exceptions import InvalidState
from senaite.astm.exceptions import NotAccepted

clients = []
envs = defaultdict(dict)
TIMEOUT = 1


async def timeout(timeout=15, callback=None):
    loop = asyncio.get_running_loop()
    try:
        now = loop.time()
        logger.info("timeout in {} seconds".format(timeout))
        await asyncio.sleep(timeout, loop=loop)
    except asyncio.CancelledError:
        logger.debug("timeout cancelled after {:.2f} seconds"
                     .format(loop.time() - now))
        return
    if callable(callback):
        callback()


class ASTMProtocol(asyncio.Protocol):
    """ASTM Protocol

    Responsible for communication and collecting complete and valid messages.
    """
    def __init__(self):
        logger.debug("ASTMProtocol:constructor")
        self.timer = asyncio.create_task(timeout(TIMEOUT, self.on_timeout))

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
        return self.env.get("chunks", [])

    @chunks.setter
    def chunks(self, value):
        self.env["chunks"] = value

    def append_chunk(self, chunk):
        chunks = self.chunks
        chunks.append(chunk)
        self.chunks = chunks

    @property
    def messages(self):
        return self.env.get("messages", [])

    @messages.setter
    def messages(self, value):
        self.env["messages"] = value

    @property
    def in_transfer_state(self):
        return self.env.get("in_transfer_state", False)

    @in_transfer_state.setter
    def in_transfer_state(self, value):
        self.env["in_transfer_state"] = bool(value)

    def data_received(self, data):
        """Called when some data is received.
        """
        import time
        time.sleep(2)
        if self.timer.done():
            return
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
            self.write_messages(self.messages)
            self.discard_env()
        else:
            raise InvalidState('Server is not ready to accept EOT message.')

    def on_timeout(self):
        """Calls when timeout event occurs. Used to limit waiting time for
        response data."""
        logger.debug("on_timeout")
        self.transport.close()

    def on_message(self, data):
        """Calls on ASTM message receiving."""
        logger.debug('on_message: %r', data)
        if not self.in_transfer_state:
            self.discard_chunked_messages()
            return NAK
        else:
            try:
                self.process_message(data)
                return ACK
            except Exception as exc:
                logger.error('Error occurred on message handling. {!r}'
                             .format(exc))
                return NAK

    def process_message(self, message):
        """Process message chunks
        """
        is_chunked_transfer = is_chunked_message(message)
        if is_chunked_transfer:
            self.append_chunk(message)
        elif self.chunks:
            self.append_chunk(message)
            self.dispatch_message(join(self.chunks))
            self.discard_chunked_messages()
        else:
            self.dispatch_message(message)

    def dispatch_message(self, message):
        logger.info('Complete Message: {!s}'.format(message))
        self.validate_checksum(message)
        messages = self.messages
        messages.append(message)
        self.messages = messages

    def write_messages(self, messages):
        """Write message to file
        """
        now = datetime.now()
        ts = now.strftime("%Y%m%d%H%M%S")
        filename = "{}.txt".format(ts)
        with open(filename, "wb") as f:
            f.writelines(messages)

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
        self.env = {}

    def connection_lost(self, ex):
        """Called when the connection is lost or closed.
        """
        logger.debug('Connection lost: {!s}'.format(self.client))
        # remove the connected client
        clients.remove(self)
