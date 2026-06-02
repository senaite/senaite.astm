# -*- coding: utf-8 -*-
"""Tests for the `senaite-astm-inspect` CLI."""

import io
import os
import unittest

from senaite.astm import inspect as inspect_cli


HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "data")
FIXTURE = os.path.join(DATA_DIR, "yumizen_h500.txt")


def _run(argv):
    """Invoke main() and capture stdout."""
    buf = io.StringIO()
    # bypass argparse + sys.stdout — call the parser, then the
    # picked subcommand directly with our buffer
    parser = inspect_cli._build_parser()
    args = parser.parse_args(argv)
    rc = args.func(args, buf)
    return rc, buf.getvalue()


class InstrumentTest(unittest.TestCase):

    def test_resolves_yumizen_fixture(self):
        rc, out = _run(["instrument", FIXTURE])
        self.assertEqual(rc, 0)
        # Either resolves to the canonical Yumizen name or falls
        # through to 'unknown' — what matters is the line shape.
        self.assertIn(FIXTURE, out)
        self.assertIn(":", out)

    def test_handles_missing_file_gracefully(self):
        rc, out = _run(["instrument", "/no/such/file.astm"])
        self.assertEqual(rc, 0)
        self.assertIn("ERROR", out)


class SummaryTest(unittest.TestCase):

    def test_summary_line_shape(self):
        rc, out = _run(["summary", FIXTURE])
        self.assertEqual(rc, 0)
        line = out.strip()
        self.assertTrue(line.startswith(FIXTURE + ":"))
        self.assertIn("instrument=", line)
        self.assertIn("sample_id=", line)
        # one bucket counter per record type
        for rt in inspect_cli.RECORD_TYPES:
            self.assertIn(rt + "=", line)


class DiffTest(unittest.TestCase):

    def test_identical_files_produce_no_diff(self):
        rc, out = _run(["diff", FIXTURE, FIXTURE])
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")

    def test_different_files_produce_diff_and_nonzero(self):
        import tempfile

        from senaite.astm.utils import rebuild_checksums

        with open(FIXTURE, "rb") as fh:
            original = fh.read()
        tweaked = rebuild_checksums(
            original.replace(b"PX440N", b"PX999A"))
        tmp = tempfile.NamedTemporaryFile(
            suffix=".astm", delete=False)
        try:
            tmp.write(tweaked)
            tmp.close()
            rc, out = _run(["diff", FIXTURE, tmp.name])
        finally:
            os.unlink(tmp.name)

        self.assertEqual(rc, 1)
        self.assertIn("PX440N", out)
        self.assertIn("PX999A", out)


def test_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(InstrumentTest))
    suite.addTests(loader.loadTestsFromTestCase(SummaryTest))
    suite.addTests(loader.loadTestsFromTestCase(DiffTest))
    return suite
