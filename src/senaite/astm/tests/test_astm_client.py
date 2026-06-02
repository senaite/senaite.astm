# -*- coding: utf-8 -*-
"""Client (connect) mode tests.

In client mode senaite.astm actively connects OUT to an instrument or
serial-to-LAN gateway that behaves as a passive TCP server (e.g. a Lantronix
configured with "Accept Incoming = Yes" / "Active Connect = None"). This is the
inverse of the server tests: here the *instrument* listens and senaite.astm
initiates the connection, then plays the receiver side of the ASTM handshake.
"""

import asyncio
import json

from senaite.astm import logger
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.constants import EOT
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.server import connect_forever
from senaite.astm.tests.base import ASTMTestBase

FIXTURE = "cobas_c111.txt"


class ASTMClientTest(ASTMTestBase):
    """senaite.astm as the TCP client connecting to a passive instrument."""

    PORT = 7984

    async def asyncSetUp(self):
        logger.info("\n------------> asyncSetUp client")
        self.loop = asyncio.get_event_loop()
        self.queue = asyncio.Queue()
        path = self.get_instrument_file_path(FIXTURE)
        self.data = self.read_file_lines(path)
        # Stand up the fake passive instrument (it listens, we connect to it)
        self.instrument = await asyncio.start_server(
            self.instrument_handler, host=self.HOST, port=self.PORT)

    async def asyncTearDown(self):
        self.instrument.close()
        await self.instrument.wait_closed()

    async def instrument_handler(self, reader, writer):
        """Play the instrument (sender) side: ENQ -> frames -> EOT."""
        writer.write(ENQ)
        await writer.drain()
        if await reader.readexactly(1) != ACK:
            writer.close()
            return
        for line in self.data:
            writer.write(line)
            await writer.drain()
            await reader.readexactly(1)  # ACK per frame
        writer.write(EOT)
        await writer.drain()
        writer.close()

    def protocol_factory(self, on_connection_lost):
        return ASTMProtocol(
            queue=self.queue,
            message_format="json",
            on_connection_lost=on_connection_lost)

    def start_client(self):
        return self.loop.create_task(
            connect_forever(
                self.loop, self.HOST, self.PORT,
                self.protocol_factory, reconnect_delay=1))

    async def test_client_collects_envelope(self):
        """The client connects out and a full session lands on the queue
        as the same JSON envelope the server mode produces."""
        logger.info("\n------------> TEST: client_collects_envelope")
        task = self.start_client()
        try:
            payload = await asyncio.wait_for(self.queue.get(), timeout=5)
        finally:
            task.cancel()
        envelope = json.loads(payload)
        self.assertIn("metadata", envelope)
        self.assertIn("H", envelope)
        self.assertIn("astm", envelope["metadata"])

    async def test_client_reconnects_after_drop(self):
        """After the instrument closes the socket, the client reconnects
        and collects the next session."""
        logger.info("\n------------> TEST: client_reconnects_after_drop")
        task = self.start_client()
        try:
            first = await asyncio.wait_for(self.queue.get(), timeout=5)
            # instrument closed after EOT -> client reconnects (1s) and the
            # instrument serves a second session
            second = await asyncio.wait_for(self.queue.get(), timeout=8)
        finally:
            task.cancel()
        self.assertTrue(first)
        self.assertTrue(second)
