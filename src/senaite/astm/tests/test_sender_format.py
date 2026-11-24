# -*- coding: utf-8 -*-
"""Tests for the `senaite-astm-send` message-format machinery.

The `-m / --message-format` option lets the CLI replay a captured
ASTM file into a SENAITE LIMS in the same JSON envelope the live
`senaite-astm-server` produces — the cermel-side adapter expects
the typed envelope, not raw bytes.

These tests cover:

- :func:`senaite.astm.utils.parse_capture` round-trip on a real
  capture file.
- :func:`senaite.astm.sender._file_to_message` for each supported
  format.
"""

import io
import json
import os
import unittest

from senaite.astm.sender import _file_to_message
from senaite.astm.utils import parse_capture


HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "data")


def _captured(filename):
    """Return the bytes of a captured ASTM file."""
    with open(os.path.join(DATA_DIR, filename), "rb") as fh:
        return fh.read()


class ParseCaptureTest(unittest.TestCase):
    """The capture parser splits a raw byte stream into ASTM frames
    by walking STX/ETX boundaries — naive line splitting fails
    because record-terminator CRs land mid-frame."""

    def test_yumizen_capture_yields_one_frame_per_record(self):
        raw = _captured("yumizen_h500.txt")
        frames = parse_capture(raw)
        self.assertGreater(len(frames), 0)
        for frame in frames:
            # STX at the start, 2-byte checksum at the end.
            self.assertTrue(frame.startswith(b"\x02"))
            # The byte at position -3 is the ETX.
            self.assertEqual(frame[-3:-2], b"\x03")

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(parse_capture(b""), [])

    def test_input_without_stx_returns_empty_list(self):
        self.assertEqual(parse_capture(b"just some text"), [])

    def test_truncated_frame_is_skipped(self):
        # STX without ETX -> not a complete frame.
        self.assertEqual(parse_capture(b"\x021H|\\^&|"), [])


class FileToMessageTest(unittest.TestCase):
    """`_file_to_message` is the per-file format converter the
    sender CLI uses. It must:

    - return raw bytes verbatim for `astm`;
    - parse + serialise to JSON for `json` (matches what the
      `senaite.core.lis2a.import` consumer expects);
    - parse + extract the flat LIS2-A payload for `lis2a`.
    """

    def _fh(self):
        # We use the bundled fixture rather than the production
        # captures so the test runs offline and on CI.
        return io.BytesIO(_captured("yumizen_h500.txt"))

    def test_json_format_yields_typed_envelope(self):
        msg = _file_to_message(self._fh(), "json")
        self.assertIsInstance(msg, str)
        env = json.loads(msg)
        # The 2.x envelope contract: metadata block + bucket lists.
        self.assertIn("metadata", env)
        self.assertIn("envelope_version", env["metadata"])
        # At minimum the captured Yumizen message has a header
        # and one or more result/manufacturer rows.
        self.assertEqual(len(env.get("H", [])), 1)

    def test_astm_format_returns_raw_bytes(self):
        msg = _file_to_message(self._fh(), "astm")
        self.assertIsInstance(msg, bytes)
        # Raw captures start with the STX of the first frame.
        self.assertEqual(msg[:1], b"\x02")

    def test_lis2a_format_returns_unwrapped_text(self):
        msg = _file_to_message(self._fh(), "lis2a")
        self.assertIsInstance(msg, str)
        # LIS2-A drops the STX/ETX wrapping and the checksum
        # but keeps the inner records — so the first character is
        # the record type character of the first frame.
        self.assertEqual(msg[:1], "H")


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ParseCaptureTest))
    suite.addTest(unittest.makeSuite(FileToMessageTest))
    return suite
