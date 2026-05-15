# -*- coding: utf-8 -*-
"""End-to-end smoke test: client → ASTM server → pipeline → handler.

Locks the full pipeline in one place so a refactor that moves
codec, protocol, wrapper, or pipeline around cannot silently change
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
from senaite.astm.core.handlers import serialize_envelope
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.transports.astm.protocol import ASTMProtocol
from senaite.astm.wrapper import Wrapper


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


def make_serializing_callback(loop, queue, message_format):
    """Build a frame_callback that wraps + serialises + enqueues.

    Mirrors the wiring in :mod:`senaite.astm.cli.astm_server` so the
    end-to-end test exercises the same path as the production server
    without taking a dependency on the CLI module.
    """
    def callback(client, frames):
        envelope = Wrapper(frames).to_envelope()
        payload = serialize_envelope(envelope, message_format)
        if message_format == "json":
            payload = payload.encode()
        loop.call_soon_threadsafe(queue.put_nowait, payload)
    return callback


class _FormatTestBase(ASTMTestBase):
    """Shared scaffolding for the per-format end-to-end tests."""

    PORT = None
    MESSAGE_FORMAT = None

    async def asyncSetUp(self):
        logger.info("\n------------> asyncSetUp e2e (%s)",
                    self.MESSAGE_FORMAT)
        self.queue = asyncio.Queue()
        self.loop = asyncio.get_event_loop()
        callback = make_serializing_callback(
            self.loop, self.queue, self.MESSAGE_FORMAT)
        self.server = await self.loop.create_server(
            lambda: ASTMProtocol(frame_callback=callback, timeout=15),
            host=self.HOST,
            port=self.PORT)

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def send_fixture(self, filename):
        await send_session(self, self.PORT, filename)

    async def collect_one(self, timeout=2.0):
        return await asyncio.wait_for(self.queue.get(), timeout=timeout)


class EndToEndTest(_FormatTestBase):
    """Full-pipeline smoke test against a representative fixture."""

    PORT = 7981
    MESSAGE_FORMAT = "json"

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


class LIS2AFormatTest(_FormatTestBase):
    """The "lis2a" format emits the LIS2-A flat string, not the JSON
    envelope. Lock the format down so a refactor cannot silently
    change the wire shape consumers see."""

    PORT = 7982
    MESSAGE_FORMAT = "lis2a"

    async def test_lis2a_payload_is_text(self):
        await self.send_fixture("cobas_c111.txt")
        payload = await self.collect_one()
        # lis2a payload is a decoded string, not bytes
        self.assertIsInstance(payload, str)
        # Must contain the H record marker
        self.assertIn("H|", payload)


class ASTMFormatTest(_FormatTestBase):
    """The "astm" format emits the original framed payload as text."""

    PORT = 7983
    MESSAGE_FORMAT = "astm"

    async def test_astm_payload_is_text(self):
        await self.send_fixture("cobas_c111.txt")
        payload = await self.collect_one()
        self.assertIsInstance(payload, str)
        # ASTM payload preserves STX framing
        self.assertIn("\x02", payload)
