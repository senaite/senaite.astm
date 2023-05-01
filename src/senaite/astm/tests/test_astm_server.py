# -*- coding: utf-8 -*-

import asyncio

from senaite.astm import logger
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase


class ASTMServerTest(ASTMTestBase):
    """Test ASTM Server
    """
    async def asyncSetUp(self):
        logger.info("\n------------> asyncSetUp")

        self.loop = asyncio.get_event_loop()
        self.protocol = ASTMProtocol()
        # start the server
        self.server = await self.loop.create_server(
            lambda: self.protocol, host=self.HOST, port=self.PORT)

    async def test_single_connection(self):
        logger.info("\n------------> TEST: single_connection")
        reader, writer = await asyncio.open_connection(
            self.HOST, self.PORT)
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

        for path in self.instrument_files:
            data = self.read_file_lines(path)
            # communicate each instrument 5 times
            for i in range(5):
                await self.communicate(data)

        # we expect 10 connections in the protocol environment
        self.assertTrue(len(self.protocol.environ), 10)

    async def asyncTearDown(self):
        logger.info("\n------------> asyncTearDown")
        self.server.close()
        await self.server.wait_closed()
