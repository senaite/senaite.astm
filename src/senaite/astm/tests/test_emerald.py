# -*- coding: utf-8 -*-
"""Tests for the CELL-DYN Emerald transport.

Covers the framing helpers (lines and CRC-16), the parser into the
envelope, the protocol handshake and the CLI wiring, including that a
frame is only acknowledged once it has been captured.

The bundled fixture is a result exported by a CELL-DYN Emerald 22 AL,
with the identifying information replaced and the control sum
recomputed.
"""

import asyncio
import os
import shutil
import tempfile
import unittest
from argparse import Namespace

from senaite.astm.cli import emerald_server
from senaite.astm.cli._runtime import drain_tasks
from senaite.astm.core.envelope import serialize_envelope
from senaite.astm.core.pipeline import Pipeline
from senaite.astm.transports.emerald.framing import build_line
from senaite.astm.transports.emerald.framing import crc16
from senaite.astm.transports.emerald.framing import extract_lines
from senaite.astm.transports.emerald.parser import parse
from senaite.astm.transports.emerald.parser import to_ansi
from senaite.astm.transports.emerald.protocol import EmeraldProtocol

HERE = os.path.dirname(__file__)
FIXTURE = os.path.join(HERE, "data", "emerald", "emerald22al_result.txt")

HEADER = b"EMD22AL;1;250207-000451;LABTECH\r"


def load_fixture():
    with open(FIXTURE, "rb") as fh:
        return fh.read()


def with_control_sum(frame, end="END_RESULT"):
    """Appends the control sum line to the frame
    """
    return frame + build_line(end, crc16(frame))


def split_frame(raw):
    """Returns the frame without the control sum line, and the control sum
    """
    pos = raw.rfind(b"END_RESULT;")
    return raw[:pos], int(raw[pos + len(b"END_RESULT;"):].strip())


class FakeTransport(object):

    def __init__(self):
        self.written = []

    def write(self, data):
        self.written.append(data)

    def get_extra_info(self, name):
        return ("127.0.0.1", 50000)


class FramingTest(unittest.TestCase):

    def test_crc16_of_exported_result(self):
        frame, control_sum = split_frame(load_fixture())
        self.assertEqual(crc16(frame), control_sum)

    def test_crc16_detects_changes(self):
        frame, control_sum = split_frame(load_fixture())
        tampered = frame.replace(b"WBC;6.9", b"WBC;9.6")
        self.assertNotEqual(crc16(tampered), control_sum)

    def test_extract_lines_keeps_partial_tail(self):
        lines, rest = extract_lines(b"CONNECT;1;9\rRESULT_RE")
        self.assertEqual(lines, [b"CONNECT;1;9\r"])
        self.assertEqual(rest, b"RESULT_RE")

    def test_extract_lines_accepts_crlf(self):
        lines, rest = extract_lines(b"A;1\r\nB;2\r")
        self.assertEqual(lines, [b"A;1\r\n", b"B;2\r"])
        self.assertEqual(rest, b"")

    def test_build_line(self):
        self.assertEqual(build_line("ACK_CONNECT", "9"), b"ACK_CONNECT;9\r")
        self.assertEqual(build_line("ACK_RESULT_READY"),
                         b"ACK_RESULT_READY\r")


class ParserTest(unittest.TestCase):

    def setUp(self):
        self.envelope = parse(load_fixture())

    def test_header_holds_the_sender(self):
        header = self.envelope.H[0]
        self.assertEqual(header["sender"]["name"], "EMD22AL")
        self.assertEqual(header["sender"]["number"], "1")
        self.assertEqual(header["sender"]["serial"], "250207-000451")
        self.assertEqual(header["operator"], "LABTECH")
        self.assertEqual(header["timestamp"], "20240219101449")

    def test_order_holds_the_sample_id(self):
        self.assertEqual(len(self.envelope.O), 1)
        order = self.envelope.O[0]
        self.assertEqual(order["sample_id"], "2600009")
        self.assertEqual(order["test"], {"name": "DIF"})

    def test_patient(self):
        patient = self.envelope.P[0]
        self.assertEqual(patient["id"], "P00000123")
        self.assertEqual(patient["birthdate"], "19800101")
        self.assertEqual(patient["sex"], "M")

    def test_parameters_are_decoded_by_token(self):
        names = [r["test"]["name"] for r in self.envelope.R]
        self.assertEqual(len(names), 22)
        for name in ("WBC", "RBC", "HGB", "HCT", "PLT", "NEU%", "LYM%",
                     "MON%", "EOS%", "BAS%", "MCV", "MCH", "MCHC"):
            self.assertIn(name, names)

    def test_result_record(self):
        wbc = self.envelope.R[0]
        self.assertEqual(wbc["test"], {"name": "WBC"})
        self.assertEqual(wbc["value"], "6.9")
        self.assertEqual(wbc["abnormal_flag"], [{"flag": "*"}])
        self.assertEqual(wbc["references"], {
            "low_panic": "3.7", "low": "3.7",
            "high": "10.1", "high_panic": "10.1"})
        self.assertEqual(wbc["completed_at"], "20240219101449")
        self.assertEqual(wbc["units"], "")

    def test_histograms_and_matrices_are_not_parameters(self):
        names = [r["test"]["name"] for r in self.envelope.R]
        self.assertFalse([n for n in names if n.startswith(("Z", "N1"))])

    def test_alarms_and_messages_as_comments(self):
        sources = [c["source"] for c in self.envelope.C]
        self.assertIn("ALARMS", sources)

    def test_metadata(self):
        metadata = self.envelope.metadata
        self.assertEqual(metadata.emerald, load_fixture().decode("utf-8"))
        self.assertEqual(metadata.frame_id, "RESULT")
        self.assertEqual(metadata.mode, "NORMAL")
        self.assertEqual(metadata.unit_system, "1")

    def test_serialize_raw_frame(self):
        raw = serialize_envelope(self.envelope, "emerald")
        self.assertEqual(raw, load_fixture().decode("utf-8"))

    def test_qc_result_has_no_sample(self):
        frame = HEADER + (
            b"RESULT\rDATE;13/05/2008\rTIME;15:04:05\rMODE;QC\rUNIT;1\r"
            b"SEQ;4\rLOT;KDH95211\rLEVEL;H\rTEST;DIF\r"
            b"WBC;8.0 ;;H;4.0 ;6.2\r")
        envelope = parse(with_control_sum(frame))
        self.assertEqual(envelope.O, [])
        self.assertEqual(envelope.P, [])
        self.assertEqual(envelope.metadata.mode, "QC")
        wbc = envelope.R[0]
        self.assertEqual(wbc["abnormal_flag"], [{"flag": "H"}])
        self.assertEqual(wbc["references"], {"low": "4.0", "high": "6.2"})

    def test_over_range_and_invalid_values(self):
        frame = HEADER + (
            b"RESULT\rDATE;13/05/2008\rTIME;15:04:05\rMODE;NORMAL\r"
            b"SID;1\rWBC;+++++;;D;2.0;4.0;11.0;15.0\r"
            b"RBC;-----;*;;2.5;4.0;6.2;7.0\r")
        envelope = parse(with_control_sum(frame))
        values = [(r["test"]["name"], r["value"]) for r in envelope.R]
        self.assertEqual(values, [("WBC", "+++++"), ("RBC", "-----")])

    def test_not_a_frame(self):
        with self.assertRaises(ValueError):
            parse(b"GARBAGE")

    def test_to_ansi(self):
        self.assertEqual(to_ansi("19/02/2024", "11:46:47"),
                         "20240219114647")
        self.assertEqual(to_ansi("19/02/2024"), "20240219")
        self.assertEqual(to_ansi(""), "")


class ProtocolTest(unittest.TestCase):

    def setUp(self):
        self.frames = []
        self.protocol = EmeraldProtocol(frame_callback=self.callback)
        self.transport = FakeTransport()
        self.protocol.connection_made(self.transport)

    def callback(self, client, frame):
        self.frames.append(frame)

    def test_connect_is_acknowledged_with_the_format_version(self):
        self.protocol.data_received(b"CONNECT;250207-000451;5\r")
        self.assertEqual(self.transport.written, [b"ACK_CONNECT;5\r"])
        self.assertEqual(self.protocol.serial, "250207-000451")

    def test_result_handshake(self):
        raw = load_fixture()
        self.protocol.data_received(HEADER + b"RESULT_READY;6582\r")
        self.assertEqual(self.transport.written, [b"ACK_RESULT_READY\r"])
        # the result arrives in small TCP segments
        for pos in range(0, len(raw), 100):
            self.protocol.data_received(raw[pos:pos + 100])
        self.assertEqual(self.frames, [split_frame(raw)[0]])
        self.assertEqual(self.transport.written[-1], b"ACK_RESULT;OK\r")

    def test_control_sum_mismatch(self):
        frame, control_sum = split_frame(load_fixture())
        tampered = frame.replace(b"WBC;6.9", b"WBC;9.6")
        self.protocol.data_received(
            tampered + build_line("END_RESULT", control_sum))
        self.assertEqual(self.frames, [])
        self.assertEqual(self.transport.written,
                         [b"ACK_RESULT;CRC_ERROR\r"])

    def test_calibration_report(self):
        frame = HEADER + (
            b"CALIBRATION;1;30/10/2003;15:36:38;LOT123;01/01/2004;"
            b"01/01/2003;10:00:00;1;1.0;1.0;1.0;1.0;1.0;0\r"
            b"WBC;11.0;0.5\r")
        self.protocol.data_received(with_control_sum(frame, "END_CALI"))
        self.assertEqual(self.frames, [frame])
        self.assertEqual(self.transport.written,
                         [b"ACK_CALI;LOT123;OK\r"])

    def test_startup_is_dispatched_without_acknowledge(self):
        self.protocol.data_received(
            HEADER + b"STARTUP;07/11/2016;16:22:47;PASSED;0.1;0.1;0.1;5\r")
        self.assertEqual(len(self.frames), 1)
        self.assertEqual(self.transport.written, [])

    def test_failing_callback_is_acknowledged_with_error(self):
        def failing(client, frame):
            raise RuntimeError("boom")
        self.protocol.frame_callback = failing
        self.protocol.data_received(load_fixture())
        self.assertEqual(self.transport.written, [b"ACK_RESULT;ERROR\r"])

    def test_disconnect(self):
        self.protocol.data_received(b"DISCONNECT;250207-000451\r")
        self.assertEqual(self.transport.written, [])
        self.assertEqual(self.protocol.frame, b"")


class ServerTest(unittest.IsolatedAsyncioTestCase):
    """Boots the listener with the CLI wiring, and checks a result frame
    is captured before it is acknowledged, then pushed
    """

    PORT = 7986

    async def asyncSetUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.task_set = set()
        self.pushed = []

        async def push(envelope):
            if emerald_server.is_sample_result(envelope):
                self.pushed.append(envelope)

        loop = asyncio.get_running_loop()
        callback = emerald_server.make_frame_callback(
            loop, Pipeline([push]), self.task_set, output=self.tmpdir)
        self.server = await loop.create_server(
            lambda: EmeraldProtocol(frame_callback=callback),
            host="127.0.0.1", port=self.PORT)

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()
        await drain_tasks(self.task_set, grace_seconds=2)

    async def read_line(self, reader):
        return await asyncio.wait_for(reader.readuntil(b"\r"), timeout=2)

    async def test_result_is_captured_acknowledged_and_pushed(self):
        reader, writer = await asyncio.open_connection(
            "127.0.0.1", self.PORT)
        try:
            writer.write(b"CONNECT;250207-000451;9\r")
            self.assertEqual(await self.read_line(reader),
                             b"ACK_CONNECT;9\r")

            writer.write(HEADER + b"RESULT_READY;6582\r")
            self.assertEqual(await self.read_line(reader),
                             b"ACK_RESULT_READY\r")

            writer.write(load_fixture())
            self.assertEqual(await self.read_line(reader),
                             b"ACK_RESULT;OK\r")

            # captured before the acknowledge was sent
            captures = os.listdir(self.tmpdir)
            self.assertEqual(len(captures), 1)
            with open(os.path.join(self.tmpdir, captures[0]), "rb") as f:
                self.assertEqual(f.read(), split_frame(load_fixture())[0])
        finally:
            writer.close()
            await writer.wait_closed()

        await drain_tasks(self.task_set, grace_seconds=2)
        self.assertEqual(len(self.pushed), 1)
        self.assertEqual(self.pushed[0].O[0]["sample_id"], "2600009")

    async def test_qc_result_is_captured_but_not_pushed(self):
        frame = HEADER + (
            b"RESULT\rDATE;13/05/2008\rTIME;15:04:05\rMODE;QC\r"
            b"WBC;8.0 ;;H;4.0 ;6.2\r")
        reader, writer = await asyncio.open_connection(
            "127.0.0.1", self.PORT)
        try:
            writer.write(with_control_sum(frame))
            self.assertEqual(await self.read_line(reader),
                             b"ACK_RESULT;OK\r")
        finally:
            writer.close()
            await writer.wait_closed()

        await drain_tasks(self.task_set, grace_seconds=2)
        self.assertEqual(len(os.listdir(self.tmpdir)), 1)
        self.assertEqual(self.pushed, [])


class CLIBuildPipelineTest(unittest.TestCase):

    def test_capture_only_without_session(self):
        args = Namespace(retries=1, delay=0, consumer="x",
                         message_format="json")
        pipeline = emerald_server.build_pipeline(args, None)
        self.assertEqual(len(pipeline), 0)

    def test_default_consumer_resolves_importer_by_sender(self):
        parser = emerald_server.build_arg_parser()
        args = parser.parse_args([])
        self.assertEqual(args.consumer, "senaite.core.lis2a.import")
        self.assertEqual(args.port, "1200")
