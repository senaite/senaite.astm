# -*- coding: utf-8 -*-

import asyncio

from senaite.astm import logger
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.constants import EOT
from senaite.astm.constants import NAK
from senaite.astm.constants import STX

instruments = []


class ASTMProtocol(asyncio.Protocol):
    """ASTM Protocol
    """

    def __init__(self):
        pass

    def connection_made(self, transport):
        """Called when a connection is made.
        """
        self.transport = transport
        peername = transport.get_extra_info('peername')
        self.instrument = "{:s}:{:d}".format(*peername)

        print('Connection from {}'.format(peername))
        # remember the connected instrument
        instruments.append(self)

    def data_received(self, data):
        """Called when some data is received.
        """
        logger.debug('Data received: {!r}'.format(data))
        self.dispatch(data)

    def dispatch(self, data):
        """Dispatcher for received data

        Lookup dispatcher for the connected IP from the config
        """
        if data.startswith(ENQ):
            resp = self.on_enq(data)
        elif data.startswith(ACK):
            resp = self.on_ack(data)
        elif data.startswith(NAK):
            resp = self.on_nak(data)
        elif data.startswith(EOT):
            resp = self.on_eot(data)
        elif data.startswith(STX):
            resp = self.on_message(data)
        else:
            resp = self.default_handler(data)

        if resp is not None:
            self.transport.write(resp)

    def connection_lost(self, ex):
        """Called when the connection is lost or closed.
        """
        print('Collection lost: {!s}'.format(self.instrument))
        # remove the instrument
        instruments.remove(self)

    def default_handler(self, data):
        raise ValueError('Unable to dispatch data: %r', data)

    def on_enq(self, data):
        """Calls on <ENQ> message receiving."""
        logger.warning('on_enq: %r', data)
        return ACK

    def on_ack(self, data):
        """Calls on <ACK> message receiving."""
        logger.warning('on_ack: %r', data)

    def on_nak(self, data):
        """Calls on <NAK> message receiving."""
        logger.warning('on_nak: %r', data)

    def on_eot(self, data):
        """Calls on <EOT> message receiving."""
        logger.warning('on_eot: %r', data)

    def on_message(self, data):
        """Calls on ASTM message receiving."""
        logger.warning('on_message: %r', data)
        return ACK

    def on_timeout(self, data):
        """Calls when timeout event occurs. Used to limit waiting time for
        response data."""
        logger.warning('Communication timeout: %r', data)
        return NAK
