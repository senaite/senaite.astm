# -*- coding: utf-8 -*-
"""Tests for CELL-DYN Emerald auto-detection on `senaite-astm-send -i`.

The frames captured by `senaite-emerald-server`, and the results exported
by the instrument to a USB drive, can be replayed into SENAITE with the
same CLI as the ASTM and HL7 captures, e.g. once the importer is
available, for the results received while the server ran capture-only.
"""

import io
import json
import os
import unittest

from senaite.astm.sender import PHI_REDACTION
from senaite.astm.sender import _detect_wire_format
from senaite.astm.sender import _file_to_message


HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "data")
# exported by the instrument: the frame and its control sum line
EXPORT = os.path.join(DATA_DIR, "emerald", "emerald22al_result.txt")
ASTM_FIXTURE = os.path.join(DATA_DIR, "yumizen_h500.txt")
HL7_FIXTURE = os.path.join(DATA_DIR, "hl7", "hemoscreen_fresh_blood.hl7")


def read(path):
    with open(path, "rb") as fh:
        return fh.read()


def capture():
    """Returns the frame as written by `senaite-emerald-server`, that is
    without the control sum line
    """
    raw = read(EXPORT)
    return raw[:raw.rfind(b"END_RESULT;")]


class DetectWireFormatTest(unittest.TestCase):

    def test_exported_result_detected(self):
        self.assertEqual(_detect_wire_format(read(EXPORT)), "emerald")

    def test_captured_result_detected(self):
        self.assertEqual(_detect_wire_format(capture()), "emerald")

    def test_crlf_line_endings(self):
        raw = capture().replace(b"\r", b"\r\n")
        self.assertEqual(_detect_wire_format(raw), "emerald")

    def test_other_formats_unchanged(self):
        self.assertEqual(_detect_wire_format(read(ASTM_FIXTURE)), "astm")
        self.assertEqual(_detect_wire_format(read(HL7_FIXTURE)), "hl7")
        self.assertEqual(_detect_wire_format(b""), "astm")

    def test_machine_name_is_required(self):
        # the same layout from another instrument is not an Emerald frame
        for header in (b"XN-550;1;310618-000034;LABTECH",
                       b"EMD22;1;310618-000034;LABTECH",
                       b"emd22al;1;310618-000034;LABTECH"):
            self.assertEqual(
                _detect_wire_format(header + b"\rRESULT\rDATE;19/02/2024\r"),
                "astm", header)

    def test_serial_number_is_required(self):
        # 13 characters, including the '-'
        for header in (b"EMD22AL;1;;LABTECH",
                       b"EMD22AL;1;310618000034;LABTECH",
                       b"EMD22AL;1;31061-8000034;LABTECH",
                       b"EMD22AL;123;310618-000034;LABTECH"):
            self.assertEqual(
                _detect_wire_format(header + b"\rRESULT\r"), "astm",
                header)

    def test_empty_user_login(self):
        self.assertEqual(
            _detect_wire_format(b"EMD22AL;1;310618-000034;\rRESULT\r"),
            "emerald")

    def test_frame_id_is_required(self):
        # a frame header alone, or followed by another frame ID, is not a
        # result frame
        self.assertEqual(
            _detect_wire_format(b"EMD22AL;1;310618-000034;LABTECH\r"),
            "astm")
        self.assertEqual(
            _detect_wire_format(
                b"EMD22AL;1;310618-000034;LABTECH\rSTARTUP\r"),
            "astm")


class EmeraldInputEndToEndTest(unittest.TestCase):

    def message(self, raw, **kw):
        return json.loads(_file_to_message(io.BytesIO(raw), "json", **kw))

    def test_captured_result_yields_typed_envelope(self):
        env = self.message(capture())
        self.assertEqual(env["H"][0]["sender"]["name"], "EMD22AL")
        self.assertEqual(env["O"][0]["sample_id"], "2600009")
        self.assertEqual(len(env["R"]), 22)
        self.assertTrue(env["metadata"]["emerald"])
        self.assertEqual(env["metadata"].get("astm", ""), "")

    def test_exported_result_yields_the_same_records(self):
        exported = self.message(read(EXPORT))
        captured = self.message(capture())
        for key in ("H", "P", "O", "R", "C"):
            self.assertEqual(exported[key], captured[key])

    def test_scrub_phi_clears_emerald_metadata(self):
        # the raw frame holds the patient's name and ID: with scrub it
        # must be cleared, as the patient record is
        plain = self.message(capture())
        scrubbed = self.message(capture(), scrub_phi=True)
        self.assertIn(b"DOE^JANE", plain["metadata"]["emerald"].encode())
        self.assertEqual(scrubbed["metadata"].get("emerald", ""), "")
        self.assertEqual(scrubbed["P"][0]["name"], PHI_REDACTION)
        # the results are kept
        self.assertEqual(scrubbed["R"], plain["R"])


def test_suite():
    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    suite.addTests(loader.loadTestsFromTestCase(DetectWireFormatTest))
    suite.addTests(loader.loadTestsFromTestCase(EmeraldInputEndToEndTest))
    return suite
