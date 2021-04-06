# -*- coding: utf-8 -*-

import asyncio
from collections import defaultdict

from senaite.astm import logger
from senaite.astm.request import Request

clients = []
envs = defaultdict(dict)


class ASTMProtocol(asyncio.Protocol):
    """ASTM Protocol
    """

    def __init__(self):
        logger.debug("ASTMProtocol:constructor")

    def connection_made(self, transport):
        """Called when a connection is made.
        """
        self.transport = transport
        peername = transport.get_extra_info('peername')
        self.ip, self.port = peername
        self.client = "{:s}:{:d}".format(*peername)
        self.env = envs[self.ip]
        logger.debug('Connection from {}'.format(peername))
        # remember the connected client
        clients.append(self)

    def data_received(self, data):
        """Called when some data is received.
        """
        logger.debug('-> Data received: {!r}'.format(data))
        self.log(data)
        request = Request(data, self.env, transport=self.transport)
        response = request()
        if response is not None:
            logger.debug('<- Sending response: {!r}'.format(response))
            self.transport.write(response)

    def connection_lost(self, ex):
        """Called when the connection is lost or closed.
        """
        logger.debug('Connection lost: {!s}'.format(self.client))
        # remove the connected client
        clients.remove(self)

    def log(self, data):
        with open("{}.log".format(self.ip), "ab") as f:
            f.write(data)
