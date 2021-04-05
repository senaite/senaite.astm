# -*- coding: utf-8 -*-

import asyncio

from senaite.astm import logger
from senaite.astm.request import Request

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

        logger.debug('Connection from {}'.format(peername))
        # remember the connected instrument
        instruments.append(self)

    def data_received(self, data):
        """Called when some data is received.
        """
        logger.debug('-> Data received: {!r}'.format(data))
        request = Request(data, transport=self.transport)
        response = request()
        if response is not None:
            logger.debug('<- Sending response: {!r}'.format(response))
            self.transport.write(response)

    def connection_lost(self, ex):
        """Called when the connection is lost or closed.
        """
        logger.debug('Collection lost: {!s}'.format(self.instrument))
        # remove the instrument
        instruments.remove(self)
