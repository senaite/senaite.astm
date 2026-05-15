# -*- coding: utf-8 -*-
"""End-to-end tests for the HL7 transport.

Boots the real listener on a local port, replays each bundled
HemoScreen HL7 fixture against it, and asserts:

- the listener writes the captured payload to ``--output``;
- the listener responds with a comm-level ACK^R01 wrapped in MLLP;
- the ACK echoes the inbound Message Control ID (MSH-10);
- the ACK uses MSA|AA when the input parses.
"""

import asyncio
import os
import tempfile
import unittest

from senaite.astm.cli import hl7_server
from senaite.astm.cli._runtime import drain_tasks
from senaite.astm.cli._runtime import make_tracked_dispatcher
from senaite.astm.core.pipeline import Pipeline
from senaite.astm.transports.hl7.framing import extract_messages, wrap
from senaite.astm.transports.hl7.protocol import HL7Protocol
from senaite.astm.transports.hl7.protocol import build_ack


HERE = os.path.dirname(__file__)
FIXTURE_DIR = os.path.join(HERE, "data", "hl7")


def load_fixture(name):
    with open(os.path.join(FIXTURE_DIR, name), "rb") as fh:
        # Normalise newlines to HL7 segment terminators.
        return fh.read().replace(b"\r\n", b"\r").replace(b"\n", b"\r") \
            .rstrip(b"\r")


class BuildAckTest(unittest.TestCase):

    def test_ack_echoes_message_control_id(self):
        fixture = load_fixture("hemoscreen_fresh_blood.hl7")
        ack = build_ack(fixture)
        # MSA|AA|<control-id> where the control id from the fixture
        # is "0" (MSH-10).
        self.assertIn(b"MSA|AA|0", ack)

    def test_ack_carries_encoding_characters(self):
        fixture = load_fixture("hemoscreen_quality_control.hl7")
        ack = build_ack(fixture)
        self.assertIn(b"|^~\\&|", ack)

    def test_ack_message_type_is_ack_r01(self):
        fixture = load_fixture("hemoscreen_proficiency.hl7")
        ack = build_ack(fixture)
        self.assertIn(b"ACK^R01", ack)

    def test_ack_falls_back_for_unparseable_msh(self):
        # build_ack should still produce a usable ACK even when the
        # MSH is missing.
        ack = build_ack(b"GARBAGE")
        self.assertIn(b"MSH|", ack)
        self.assertIn(b"MSA|AA|", ack)


class HL7ServerTest(unittest.IsolatedAsyncioTestCase):

    PORT = 7985

    async def asyncSetUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(self._cleanup_tmpdir)

        self.task_set = set()
        self.received = []

        async def capture(payload):
            self.received.append(payload)

        self.pipeline = Pipeline([capture])
        self.loop = asyncio.get_event_loop()
        dispatch = make_tracked_dispatcher(
            self.loop, self.pipeline, self.task_set)
        self.server = await self.loop.create_server(
            lambda: HL7Protocol(frame_callback=dispatch),
            host="127.0.0.1", port=self.PORT)

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()
        await drain_tasks(self.task_set, grace_seconds=2)

    def _cleanup_tmpdir(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    async def _send_and_recv(self, payload):
        reader, writer = await asyncio.open_connection("127.0.0.1",
                                                       self.PORT)
        try:
            writer.write(wrap(payload))
            await writer.drain()

            buffer = b""
            for _ in range(10):
                chunk = await asyncio.wait_for(reader.read(1024),
                                               timeout=2.0)
                if not chunk:
                    break
                buffer += chunk
                messages, buffer = extract_messages(buffer)
                if messages:
                    return messages[0]
            raise AssertionError("Server did not send an ACK")
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_fresh_blood_is_dispatched_and_acked(self):
        payload = load_fixture("hemoscreen_fresh_blood.hl7")
        ack = await self._send_and_recv(payload)

        # Pipeline received the payload exactly once.
        await drain_tasks(self.task_set, grace_seconds=2)
        self.assertEqual(self.received, [payload])

        # ACK echoes the control ID and uses AA.
        self.assertIn(b"MSA|AA|0", ack)
        self.assertIn(b"ACK^R01", ack)

    async def test_quality_control_is_dispatched(self):
        payload = load_fixture("hemoscreen_quality_control.hl7")
        ack = await self._send_and_recv(payload)
        await drain_tasks(self.task_set, grace_seconds=2)
        self.assertEqual(self.received, [payload])
        # Control ID is "1" for the QC fixture.
        self.assertIn(b"MSA|AA|1", ack)

    async def test_two_messages_one_connection(self):
        """Verifies the protocol can drain multiple MLLP blocks from
        a single TCP socket."""
        first = load_fixture("hemoscreen_fresh_blood.hl7")
        second = load_fixture("hemoscreen_proficiency.hl7")

        reader, writer = await asyncio.open_connection("127.0.0.1",
                                                       self.PORT)
        try:
            writer.write(wrap(first) + wrap(second))
            await writer.drain()

            collected = []
            buffer = b""
            while len(collected) < 2:
                chunk = await asyncio.wait_for(reader.read(1024),
                                               timeout=2.0)
                if not chunk:
                    break
                buffer += chunk
                messages, buffer = extract_messages(buffer)
                collected.extend(messages)
        finally:
            writer.close()
            await writer.wait_closed()

        await drain_tasks(self.task_set, grace_seconds=2)

        self.assertEqual(len(collected), 2)
        self.assertEqual(self.received, [first, second])


class RawCaptureHandlerTest(unittest.IsolatedAsyncioTestCase):

    async def test_writes_one_file_per_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            handler = hl7_server.RawCaptureHandler(tmp)
            await handler(b"first payload")
            await asyncio.sleep(1.05)
            await handler(b"second payload")
            files = sorted(os.listdir(tmp))
            self.assertEqual(len(files), 2)
            for name in files:
                self.assertTrue(name.endswith(".hl7"))

    async def test_noop_when_path_empty(self):
        handler = hl7_server.RawCaptureHandler(path=None)
        # Must not raise and must not create anything.
        await handler(b"payload")


class CLIBuildPipelineTest(unittest.TestCase):

    def test_no_output_means_empty_pipeline(self):
        class _Args(object):
            output = None

        pipeline = hl7_server.build_pipeline(_Args())
        self.assertEqual(len(pipeline), 0)

    def test_with_output_adds_raw_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            class _Args(object):
                output = tmp

            pipeline = hl7_server.build_pipeline(_Args())
            self.assertEqual(len(pipeline), 1)
            self.assertEqual(pipeline.handlers[0].name, "raw_capture")


if __name__ == "__main__":
    unittest.main()
