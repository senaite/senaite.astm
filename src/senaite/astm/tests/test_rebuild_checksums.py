# -*- coding: utf-8 -*-
"""Tests for :func:`senaite.astm.utils.rebuild_checksums`.

Captured ASTM files often need light edits to be useful as test
fixtures (sample-id swap, PHI scrubbing). Each edit invalidates
the trailing 2-byte checksum of the affected frame, and the codec
asserts at parse time. `rebuild_checksums` recomputes every
frame's trailer in place so the edited bytes round-trip cleanly.
"""

import io
import os
import unittest

from senaite.astm.constants import STX
from senaite.astm.sender import _file_to_message
from senaite.astm.utils import make_checksum
from senaite.astm.utils import parse_capture
from senaite.astm.utils import rebuild_checksums
from senaite.astm.utils import validate_checksum


HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "data")


def _captured(filename):
    with open(os.path.join(DATA_DIR, filename), "rb") as fh:
        return fh.read()


class RebuildChecksumsTest(unittest.TestCase):

    def test_corrupt_checksum_is_corrected(self):
        raw = _captured("yumizen_h500.txt")
        # corrupt the first frame's checksum to a known-bad value
        first_frame = parse_capture(raw)[0]
        cs_offset = raw.find(first_frame) + len(first_frame) - 2
        broken = bytearray(raw)
        broken[cs_offset:cs_offset + 2] = b"00"

        fixed = rebuild_checksums(bytes(broken))
        for frame in parse_capture(fixed):
            # validate_checksum wants the full frame plus trailing
            # CRLF; the codec accepts either.
            self.assertTrue(validate_checksum(frame + b"\r\n"))

    def test_unedited_capture_round_trips_unchanged(self):
        raw = _captured("yumizen_h500.txt")
        self.assertEqual(rebuild_checksums(raw), raw)

    def test_non_frame_bytes_pass_through(self):
        # ENQ / EOT / junk surrounding a single valid frame
        body = b"5O|1|SAMPLE\rL|1|N"
        frame = STX + body + b"\x03" + make_checksum(body + b"\x03")
        stream = b"\x05" + frame + b"\r\n" + b"\x04"
        self.assertEqual(rebuild_checksums(stream), stream)

    def test_truncated_tail_passes_through(self):
        # STX without a terminator — helper must not lose bytes
        garbage = b"\x021H|\\^&|"
        self.assertEqual(rebuild_checksums(garbage), garbage)

    def test_empty_input(self):
        self.assertEqual(rebuild_checksums(b""), b"")


class SenderRebuildFlagTest(unittest.TestCase):
    """`_file_to_message(..., rebuild=True)` repairs hand-edited
    captures before the codec sees them. Off by default so real
    captures aren't silently masked."""

    def _edited_capture(self):
        raw = _captured("yumizen_h500.txt")
        # swap a record-body byte — invalidates that frame's
        # checksum (the trailer was computed over the original).
        # Replace the first lowercase 'P' of the patient record
        # type with itself plus a marker so any frame is altered.
        # Easier: substitute a digit inside a record body.
        edited = raw.replace(b"|R|", b"|F|", 1)
        self.assertNotEqual(edited, raw)
        return edited

    def test_rebuild_true_repairs_edited_capture(self):
        edited = self._edited_capture()
        msg = _file_to_message(
            io.BytesIO(edited), "astm", rebuild=True)
        # every frame now validates
        for frame in parse_capture(msg):
            self.assertTrue(validate_checksum(frame + b"\r\n"))

    def test_rebuild_false_is_default(self):
        raw = _captured("yumizen_h500.txt")
        # default path must not modify the bytes
        msg = _file_to_message(io.BytesIO(raw), "astm")
        self.assertEqual(msg, raw)


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(RebuildChecksumsTest))
    suite.addTest(unittest.makeSuite(SenderRebuildFlagTest))
    return suite
