# -*- coding: utf-8 -*-
"""Tests for HL7 auto-detection on `senaite-astm-send -i`.

senaite-astm-send was originally ASTM-only; this exercise
confirms that HL7 v2 inputs (the HemoScreen fixtures shipped in
``tests/data/hl7/``) flow through the same CLI without a
``parse_capture`` failure, and that ``--scrub-phi`` clears the
HL7 metadata payload alongside the ASTM ones.
"""

import io
import json
import os
import unittest

from senaite.astm.sender import _detect_wire_format
from senaite.astm.sender import _file_to_message


HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "data")
HL7_FIXTURE = os.path.join(
    DATA_DIR, "hl7", "hemoscreen_fresh_blood.hl7")
ASTM_FIXTURE = os.path.join(DATA_DIR, "yumizen_h500.txt")


class DetectWireFormatTest(unittest.TestCase):

    def test_hl7_message_detected(self):
        self.assertEqual(_detect_wire_format(b"MSH|^~\\&|...\r"), "hl7")

    def test_hl7_message_with_leading_whitespace(self):
        self.assertEqual(
            _detect_wire_format(b"\n\rMSH|^~\\&|...\r"), "hl7")

    def test_astm_capture_default(self):
        # ASTM captures start with ENQ / STX or a leading newline
        self.assertEqual(_detect_wire_format(b"\x051H|\\^&|"), "astm")
        self.assertEqual(_detect_wire_format(b"\x021H|\\^&|\x03B7"), "astm")

    def test_empty_input_routes_to_astm(self):
        # An empty input must not crash detection; the ASTM parser
        # will return [] frames downstream.
        self.assertEqual(_detect_wire_format(b""), "astm")


class HL7InputEndToEndTest(unittest.TestCase):

    def _fh(self, path):
        return io.BytesIO(open(path, "rb").read())

    def test_hl7_file_yields_typed_envelope(self):
        msg = _file_to_message(self._fh(HL7_FIXTURE), "json")
        env = json.loads(msg)
        # HL7 metadata carries the verbatim text; ASTM metadata
        # stays empty.
        self.assertTrue(env["metadata"].get("hl7"))
        self.assertEqual(env["metadata"].get("astm", ""), "")
        # OBX rows landed in R.
        self.assertGreater(len(env["R"]), 0)

    def test_astm_path_still_works_after_detection(self):
        msg = _file_to_message(self._fh(ASTM_FIXTURE), "json")
        env = json.loads(msg)
        self.assertEqual(len(env["H"]), 1)

    def test_scrub_phi_clears_hl7_metadata(self):
        # Without scrub the verbatim HL7 text is in metadata.hl7;
        # with scrub it must be cleared (the inner records carry
        # PID-3 sample ids and other identifiers).
        plain = json.loads(
            _file_to_message(self._fh(HL7_FIXTURE), "json"))
        scrubbed = json.loads(
            _file_to_message(
                self._fh(HL7_FIXTURE), "json", scrub_phi=True))
        self.assertTrue(plain["metadata"].get("hl7"))
        self.assertEqual(scrubbed["metadata"].get("hl7", ""), "")


def test_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(DetectWireFormatTest))
    suite.addTests(loader.loadTestsFromTestCase(HL7InputEndToEndTest))
    return suite
