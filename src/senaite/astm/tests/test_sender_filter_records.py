# -*- coding: utf-8 -*-
"""Tests for `senaite-astm-send --filter-records` / `--drop-records`.

Both flags trim the typed envelope's per-type buckets in place
before serialisation, producing a stripped fixture useful for
exercising one specific consumer path.
"""

import argparse
import json
import os
import unittest

from senaite.astm.core.envelope import Envelope
from senaite.astm.core.envelope import Metadata
from senaite.astm.sender import RECORD_TYPES
from senaite.astm.sender import _file_to_message
from senaite.astm.sender import _filter_envelope_records
from senaite.astm.sender import _parse_record_list


HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "data")
FIXTURE = os.path.join(DATA_DIR, "yumizen_h500.txt")


def _envelope(**kw):
    return json.loads(
        _file_to_message(open(FIXTURE, "rb"), "json", **kw))


class ParseRecordListTest(unittest.TestCase):

    def test_accepts_comma_separated(self):
        self.assertEqual(_parse_record_list("H,O,R"), ("H", "O", "R"))

    def test_normalises_case_and_whitespace(self):
        self.assertEqual(
            _parse_record_list(" h , o , r "),
            ("H", "O", "R"))

    def test_rejects_unknown_letter(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_record_list("H,X")

    def test_rejects_empty(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_record_list(",,")


class FilterEnvelopeTest(unittest.TestCase):

    def _populated_envelope(self):
        env = Envelope(metadata=Metadata())
        for rt in RECORD_TYPES:
            getattr(env, rt).append({"type": rt})
        return env

    def test_keep_only_listed(self):
        env = self._populated_envelope()
        _filter_envelope_records(env, ("H", "O"), None)
        self.assertEqual(env.H[0]["type"], "H")
        self.assertEqual(env.O[0]["type"], "O")
        for rt in ("P", "R", "C", "M", "L", "Q"):
            self.assertEqual(getattr(env, rt), [])

    def test_drop_removes_listed(self):
        env = self._populated_envelope()
        _filter_envelope_records(env, None, ("C", "M"))
        self.assertEqual(env.C, [])
        self.assertEqual(env.M, [])
        for rt in ("H", "P", "O", "R", "L", "Q"):
            self.assertEqual(getattr(env, rt)[0]["type"], rt)


class FilterEndToEndTest(unittest.TestCase):

    def test_filter_keeps_only_listed_buckets(self):
        env = _envelope(keep_records=("H",))
        self.assertEqual(len(env["H"]), 1)
        for rt in ("P", "O", "R", "C", "M"):
            self.assertEqual(env.get(rt, []), [])

    def test_drop_clears_listed_buckets(self):
        env_full = _envelope()
        # M (manufacturer) is populated by the Yumizen fixture.
        self.assertGreater(len(env_full.get("M", [])), 0)
        env_no_m = _envelope(drop_records=("M",))
        self.assertEqual(env_no_m["M"], [])
        # other buckets pass through unchanged
        self.assertEqual(len(env_no_m["H"]), len(env_full["H"]))


def test_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(ParseRecordListTest))
    suite.addTests(loader.loadTestsFromTestCase(FilterEnvelopeTest))
    suite.addTests(loader.loadTestsFromTestCase(FilterEndToEndTest))
    return suite
