# -*- coding: utf-8 -*-
"""Tests for `senaite-astm-send --substitute-sample-id OLD=NEW`.

The flag retargets a captured ASTM file to a different sample id
so the same fixture can be replayed against a fresh registration
without editing the file. Combines with `--rebuild-checksums` so
the trailer-invalidating edit round-trips through the codec.
"""

import argparse
import io
import os
import unittest

from senaite.astm.sender import _apply_substitutions
from senaite.astm.sender import _file_to_message
from senaite.astm.sender import _parse_substitution
from senaite.astm.utils import parse_capture
from senaite.astm.utils import validate_checksum


HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "data")
FIXTURE = "yumizen_h500.txt"


def _captured(filename):
    with open(os.path.join(DATA_DIR, filename), "rb") as fh:
        return fh.read()


class ParseSubstitutionTest(unittest.TestCase):

    def test_valid_pair_returns_bytes_tuple(self):
        old, new = _parse_substitution("AAA=BBB")
        self.assertEqual(old, b"AAA")
        self.assertEqual(new, b"BBB")

    def test_empty_new_is_allowed(self):
        # OLD=  is a delete; useful for scrubbing
        old, new = _parse_substitution("XYZ=")
        self.assertEqual((old, new), (b"XYZ", b""))

    def test_missing_equals_rejected(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_substitution("no-equals-sign")

    def test_empty_old_rejected(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_substitution("=NEW")


class ApplySubstitutionsTest(unittest.TestCase):

    def test_single_replacement(self):
        result = _apply_substitutions(
            b"hello world", [(b"world", b"there")])
        self.assertEqual(result, b"hello there")

    def test_replacements_are_global(self):
        result = _apply_substitutions(
            b"a b a b a", [(b"a", b"X")])
        self.assertEqual(result, b"X b X b X")

    def test_pairs_apply_in_order(self):
        # Order matters when later pairs see earlier substitutions
        result = _apply_substitutions(
            b"AAA", [(b"AAA", b"BBB"), (b"BBB", b"CCC")])
        self.assertEqual(result, b"CCC")

    def test_no_pairs_returns_input_verbatim(self):
        raw = b"\x021H|\\^&|"
        self.assertEqual(_apply_substitutions(raw, []), raw)


class SenderSubstituteFlagTest(unittest.TestCase):
    """End-to-end: substitution + checksum rebuild yields a
    capture whose Order record carries the new sample id and
    whose frames all validate."""

    def test_sample_id_swap_with_rebuild(self):
        raw = _captured(FIXTURE)
        # Locate the original sample id in the Order frame.
        # The Yumizen fixture's order record carries `PX440N`.
        self.assertIn(b"PX440N", raw)

        msg = _file_to_message(
            io.BytesIO(raw),
            "astm",
            rebuild=True,
            substitutions=[(b"PX440N", b"CLVB262299")])
        self.assertIn(b"CLVB262299", msg)
        self.assertNotIn(b"PX440N", msg)
        for frame in parse_capture(msg):
            self.assertTrue(validate_checksum(frame + b"\r\n"))

    def test_substitution_without_rebuild_breaks_checksum(self):
        # Documents the contract: the user must combine with
        # --rebuild-checksums or the codec asserts later.
        raw = _captured(FIXTURE)
        msg = _file_to_message(
            io.BytesIO(raw),
            "astm",
            rebuild=False,
            substitutions=[(b"PX440N", b"CLVB262299")])
        # At least one frame should now fail validation since the
        # body changed but the trailer didn't.
        bad = [f for f in parse_capture(msg)
               if not validate_checksum(f + b"\r\n")]
        self.assertGreater(len(bad), 0)


def test_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(ParseSubstitutionTest))
    suite.addTests(loader.loadTestsFromTestCase(ApplySubstitutionsTest))
    suite.addTests(loader.loadTestsFromTestCase(SenderSubstituteFlagTest))
    return suite
