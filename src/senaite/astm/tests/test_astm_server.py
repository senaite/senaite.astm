# -*- coding: utf-8 -*-

import asyncio
import os
from unittest import IsolatedAsyncioTestCase

from senaite.astm import logger
from senaite.astm.constants import ACK
from senaite.astm.constants import CRLF
from senaite.astm.constants import ENQ
from senaite.astm.protocol import ASTMProtocol

HOST = "localhost"
PORT = 7980


class ASTMServerTest(IsolatedAsyncioTestCase):
    """Test ASTM Server
    """
    async def asyncSetUp(self):
        logger.info("\n------------> asyncSetUp")

        self.loop = asyncio.get_event_loop()
        self.protocol = ASTMProtocol()
        # start the server
        self.server = await self.loop.create_server(
            lambda: self.protocol, host=HOST, port=PORT)

    async def test_single_connection(self):
        logger.info("\n------------> TEST: single_connection")
        reader, writer = await asyncio.open_connection(HOST, PORT)
        writer.write(ENQ)
        await writer.drain()
        response = await reader.read(100)
        self.assertEqual(response, ACK)
        writer.close()
        await writer.wait_closed()

    async def test_multi_connection(self):
        """Test multiple connections
        """
        logger.info("\n------------> TEST: multi_connection")
        for i in range(10):
            await self.full_instrument_communication()

        # we expect 10 connections in the protocol environment
        self.assertTrue(len(self.protocol.environ), 10)

    def get_instrument_file_path(self, filename="yumizen_h500.txt"):
        """Returns the instrument file path
        """
        test_path = os.path.dirname(__file__)
        return os.path.join(test_path, "data", filename)

    def read_file_lines(self, path, mode="rb"):
        """Read the lines of the file
        """
        with open(path, mode) as f:
            return f.readlines()

    async def full_instrument_communication(self, reader=None, writer=None):
        """Simulate a full instrument communication
        """
        if not all([reader, writer]):
            reader, writer = await asyncio.open_connection(HOST, PORT)

        # Start with an ENQ
        writer.write(ENQ)
        await writer.drain()
        response = await reader.read(100)
        self.assertEqual(response, ACK)

        # Send instrument data
        path = self.get_instrument_file_path()
        lines = self.read_file_lines(path)
        for line in lines:
            # Test fixture: Remove trailing \r\n
            message = line.strip(CRLF)
            writer.write(message)
            await writer.drain()
            response = await reader.read(100)
            # We expect an ACK as response
            self.assertEqual(response, ACK)

        # close the connection
        writer.close()
        await writer.wait_closed()

    async def asyncTearDown(self):
        logger.info("\n------------> asyncTearDown")
        self.server.close()
        await self.server.wait_closed()
