# -*- coding: utf-8 -*-

import asyncio
import os

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
        self.timeout = 15

        self.loop = asyncio.get_event_loop()
        # start the server
        self.server = await self.loop.create_server(
            lambda: ASTMProtocol(timeout=self.timeout),
            host=self.HOST, port=self.PORT)

    async def test_connection_timeout(self):
        """Test connection_timeout
        """
        logger.info("\n------------> TEST: connection_timeout")
        # set the timeout to 0.1 seconds
        self.timeout = 0.1
        reader, writer = await asyncio.open_connection(
            self.HOST, self.PORT)
        # wait until the timeout exceeded
        await asyncio.sleep(0.2)
        writer.write(ENQ)
        await writer.drain()
        response = await reader.read(100)
        self.assertEqual(response, b"")
        writer.close()
        await writer.wait_closed()
        self.timeout = 15

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
        """Test multiple sequential connections
        """
        logger.info("\n------------> TEST: multi_connection")

        for path in self.instrument_files:
            logger.info("Reading Instrument Data '%s'" %
                        os.path.basename(path))
            data = self.read_file_lines(path)
            # communicate each instrument 5 times
            for i in range(5):
                await self.communicate(data)

    async def test_multi_concurrent_connection(self):
        """Test multiple concurrent connections
        """
        logger.info("\n------------> TEST: multi_concurrent_connection")
        tasks = [self.send_instrument_data() for i in range(5)]
        await asyncio.gather(*tasks)

    async def send_instrument_data(self):
        for path in self.instrument_files:
            logger.info("Reading Instrument Data '%s'" %
                        os.path.basename(path))
            data = self.read_file_lines(path)
            # open a new connection for every instrument
            reader, writer = await asyncio.open_connection(
                self.HOST, self.PORT)
            await self.communicate(data, reader=reader, writer=writer)

    async def asyncTearDown(self):
        logger.info("\n------------> asyncTearDown")
        self.server.close()
        await self.server.wait_closed()
