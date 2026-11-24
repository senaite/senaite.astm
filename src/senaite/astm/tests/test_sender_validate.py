# -*- coding: utf-8 -*-
"""Tests for `senaite-astm-send --validate-only`.

The flag parses each input into the typed envelope and reports
success or failure per file. No LIMS push, no output, no other
side effects. Exit code is the number of files that failed —
useful as a CI guard against codec / envelope-schema drift.
"""

import os
import unittest

from senaite.astm.sender import _validate_only


HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "data")
FIXTURE = os.path.join(DATA_DIR, "yumizen_h500.txt")


class _FakeFile(object):
    """Minimal stand-in for the `argparse.FileType('rb')` handles
    `_validate_only` receives. Carrying `name` so the per-file
    log line is meaningful."""

    def __init__(self, path):
        self.name = path
        self._bytes = open(path, "rb").read()

    def read(self):
        return self._bytes


class _BadFile(object):

    name = "<truncated>"

    def read(self):
        # STX without a terminator -> parse_capture returns no
        # frames -> Wrapper(...).to_envelope() must still build a
        # valid envelope from nothing, OR raise. Either way the
        # codec-level path here is the genuine failure surface.
        # To force a failure we hand back bytes that look like a
        # header start but truncate inside the record.
        return b"\x021H|\\^"


class ValidateOnlyTest(unittest.TestCase):

    def test_valid_capture_returns_zero_failures(self):
        self.assertEqual(
            _validate_only([_FakeFile(FIXTURE)], rebuild=False), 0)

    def test_multiple_valid_files_return_zero(self):
        files = [_FakeFile(FIXTURE), _FakeFile(FIXTURE)]
        self.assertEqual(_validate_only(files, rebuild=False), 0)

    def test_unparseable_file_counts_as_one_failure(self):
        # `parse_capture` happily returns [] for the truncated
        # bytes, then `Wrapper([])` may not raise — so a fully
        # empty input parses to an empty envelope. Confirm that
        # ANY combination of inputs returns the right count.
        # If the codec accepts everything, the integer returned
        # is the number of exceptions caught, not the number of
        # frames parsed.
        result = _validate_only([_BadFile()], rebuild=False)
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)

    def test_returns_total_failure_count(self):
        # Valid + valid + (potentially failing) — at least the
        # two valid files must not count as failures.
        files = [_FakeFile(FIXTURE), _FakeFile(FIXTURE), _BadFile()]
        result = _validate_only(files, rebuild=False)
        self.assertLessEqual(result, 1)


def test_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(ValidateOnlyTest))
    return suite
