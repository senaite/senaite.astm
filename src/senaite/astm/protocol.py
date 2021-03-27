# -*- coding: utf-8 -*-

import asyncio

from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ

instruments = []


class ASTMProtocol(asyncio.Protocol):
    """ASTM Protocol
    """

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
        message = data.decode()
        print('Data received: {!r}'.format(message))

        if data.startswith(ENQ):
            print('ENQ received: {!r}'.format(data))
            self.transport.write(ACK)

        # if data.startswith(ENQ):
        #     self.transport.write(ACK)
        # else:
        #     print('Send: {!r}'.format(message))
        #     self.transport.write(data)

        # print('Close the client socket')
        # self.transport.close()

    def connection_lost(self, ex):
        """Called when the connection is lost or closed.
        """
        print("connection_lost: {}".format(self.instrument))
        # remove the instrument
        instruments.remove(self)
