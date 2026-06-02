# -*- coding: utf-8 -*-
"""End-to-end smoke test: client → ASTM server → queue → message.

Locks the full pipeline in one place so a refactor that moves
codec, protocol, wrapper, or queueing around cannot silently change
the payload downstream consumers receive. Per-format checks live
here; per-instrument record details live in the instrument-specific
tests.
"""

import asyncio
import json

from senaite.astm import logger
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.constants import EOT
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase


async def send_session(test_case, port, fixture_name):
    """ENQ + frames + EOT against `port`. Used by every format test."""
    path = test_case.get_instrument_file_path(fixture_name)
    data = test_case.read_file_lines(path)

    reader, writer = await asyncio.open_connection(test_case.HOST, port)

    writer.write(ENQ)
    await writer.drain()
    test_case.assertEqual(await reader.read(100), ACK)

    for line in data:
        writer.write(line)
        await writer.drain()
        test_case.assertEqual(await reader.read(100), ACK)

    writer.write(EOT)
    await writer.drain()

    writer.close()
    await writer.wait_closed()


class EndToEndTest(ASTMTestBase):
    """Full-pipeline smoke test against a representative fixture."""

    PORT = 7981

    async def asyncSetUp(self):
        logger.info("\n------------> asyncSetUp e2e")
        self.queue = asyncio.Queue()

        self.loop = asyncio.get_event_loop()
        self.server = await self.loop.create_server(
            lambda: ASTMProtocol(
                queue=self.queue,
                timeout=15,
                message_format="json"),
            host=self.HOST,
            port=self.PORT)

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def send_fixture(self, filename):
        """ENQ → data frames → EOT → close.

        The inherited ``communicate`` omits the trailing EOT, so the
        protocol never leaves transfer state and never pushes onto
        the queue. Queue-based assertions need the full session.
        """
        await send_session(self, self.PORT, filename)

    async def collect_one(self, timeout=2.0):
        """Pull a single envelope off the queue, with a short bound."""
        return await asyncio.wait_for(self.queue.get(), timeout=timeout)

    async def test_json_envelope_reaches_queue(self):
        """A captured Cobas C111 transcript flows through the server,
        gets wrapped, and lands on the queue as JSON bytes."""
        await self.send_fixture("cobas_c111.txt")
        payload = await self.collect_one()
        self.assertIsInstance(payload, bytes)
        envelope = json.loads(payload)
        # Top-level shape contract
        self.assertIn("metadata", envelope)
        self.assertIn("H", envelope)
        self.assertIn("O", envelope)
        self.assertIn("R", envelope)
        # Header is a list of one dict
        self.assertEqual(len(envelope["H"]), 1)
        # Metadata carries both raw representations
        self.assertIn("astm", envelope["metadata"])
        self.assertIn("lis2a", envelope["metadata"])

    async def test_one_message_per_session(self):
        """A single instrument session yields exactly one envelope."""
        await self.send_fixture("cobas_c111.txt")
        await self.collect_one()
        self.assertTrue(self.queue.empty())

    async def test_multiple_sessions_queue_independently(self):
        """Two back-to-back sessions produce two envelopes."""
        await self.send_fixture("cobas_c111.txt")
        await self.send_fixture("pentra_xlr.txt")
        first = await self.collect_one()
        second = await self.collect_one()
        # Different instruments → different metadata payloads
        self.assertNotEqual(first, second)
        self.assertTrue(self.queue.empty())


class LIS2AFormatTest(ASTMTestBase):
    """The default message format ("lis2a") emits the LIS2-A
    flat string, not the JSON envelope. Lock the format down so a
    refactor cannot silently change the wire shape consumers see."""

    PORT = 7982

    async def asyncSetUp(self):
        self.queue = asyncio.Queue()
        self.loop = asyncio.get_event_loop()
        self.server = await self.loop.create_server(
            lambda: ASTMProtocol(
                queue=self.queue,
                timeout=15,
                message_format="lis2a"),
            host=self.HOST,
            port=self.PORT)

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def test_lis2a_payload_is_text(self):
        await send_session(self, self.PORT, "cobas_c111.txt")
        payload = await asyncio.wait_for(self.queue.get(), timeout=2.0)
        # lis2a payload is a decoded string, not bytes
        self.assertIsInstance(payload, str)
        # Must contain the H record marker
        self.assertIn("H|", payload)


class ASTMFormatTest(ASTMTestBase):
    """The "astm" format emits the original framed payload as text."""

    PORT = 7983

    async def asyncSetUp(self):
        self.queue = asyncio.Queue()
        self.loop = asyncio.get_event_loop()
        self.server = await self.loop.create_server(
            lambda: ASTMProtocol(
                queue=self.queue,
                timeout=15,
                message_format="astm"),
            host=self.HOST,
            port=self.PORT)

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def test_astm_payload_is_text(self):
        await send_session(self, self.PORT, "cobas_c111.txt")
        payload = await asyncio.wait_for(self.queue.get(), timeout=2.0)
        self.assertIsInstance(payload, str)
        # ASTM payload preserves STX framing
        self.assertIn("\x02", payload)
