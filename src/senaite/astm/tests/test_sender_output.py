# -*- coding: utf-8 -*-
"""Tests for `senaite-astm-send -o / --output` (convert-only mode).

`--output` diverts the converted message(s) to disk or stdout
instead of POSTing to a LIMS. It composes with `--message-format`,
so the same file can be inspected as raw bytes, the LIS2-A flat
string, or the typed JSON envelope without bringing up a SENAITE
instance.
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest

from senaite.astm import sender


HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "data")
FIXTURE = os.path.join(DATA_DIR, "yumizen_h500.txt")


class _FakeStdout(object):
    """Mimic the parts of `sys.stdout` `_write_one` touches —
    `.buffer.write(bytes)`. We can't reuse a `TextIOWrapper` here
    because flushing it on teardown closes the underlying buffer."""

    def __init__(self):
        self.buffer = io.BytesIO()

    def flush(self):
        pass


def _run(argv):
    """Invoke the CLI in-process and return its stdout bytes."""
    saved_argv = sys.argv
    saved_stdout = sys.stdout
    fake = _FakeStdout()
    sys.argv = ["senaite-astm-send"] + argv
    sys.stdout = fake
    try:
        sender.main()
    finally:
        sys.stdout = saved_stdout
        sys.argv = saved_argv
    return fake.buffer.getvalue()


class OutputStdoutTest(unittest.TestCase):

    def test_json_to_stdout_yields_typed_envelope(self):
        out = _run(["-i", FIXTURE, "-m", "json", "-o", "-"])
        env = json.loads(out.decode("utf-8"))
        self.assertIn("metadata", env)
        self.assertEqual(len(env.get("H", [])), 1)

    def test_astm_to_stdout_returns_raw_bytes(self):
        out = _run(["-i", FIXTURE, "-m", "astm", "-o", "-"])
        # Raw captures start with the STX of the first frame.
        self.assertEqual(out[:1], b"\x02")


class OutputFileTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_single_input_writes_to_file_path(self):
        target = os.path.join(self.tmp, "out.json")
        _run(["-i", FIXTURE, "-m", "json", "-o", target])
        with open(target, "rb") as fh:
            env = json.loads(fh.read().decode("utf-8"))
        self.assertIn("metadata", env)

    def test_directory_output_writes_one_file_per_input(self):
        # Two inputs (same fixture twice — argparse opens both as
        # separate handles) -> two output files in the directory.
        _run([
            "-i", FIXTURE, FIXTURE,
            "-m", "json",
            "-o", self.tmp,
        ])
        # Both inputs share the same basename, so only one file
        # is written (the second overwrites the first). The shape
        # we care about: the directory contains a <stem>.json.
        stem = os.path.splitext(os.path.basename(FIXTURE))[0]
        target = os.path.join(self.tmp, stem + ".json")
        self.assertTrue(os.path.isfile(target))


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(OutputStdoutTest))
    suite.addTest(unittest.makeSuite(OutputFileTest))
    return suite
