# -*- coding: utf-8 -*-
"""Tests for `senaite-astm-server --capture-only`.

The flag turns the server into a hold-and-review pipeline: it
accepts connections, writes captures to disk, and skips the LIMS
push step even when --url is supplied.
"""

import unittest

from senaite.astm.cli.astm_server import build_arg_parser
from senaite.astm.cli.astm_server import build_pipeline
from senaite.astm.core.lims import LimsPushHandler
from senaite.astm.core.output import DiskCaptureHandler


class _FakeSession(object):
    pass


def _parse(extra):
    parser = build_arg_parser()
    return parser.parse_args(extra)


class BuildPipelineTest(unittest.TestCase):

    def test_capture_only_drops_lims_push(self):
        args = _parse([
            "-o", "/tmp/out",
            "-u", "http://admin:secret@localhost/senaite",
            "--capture-only",
        ])
        pipeline = build_pipeline(args, _FakeSession())
        kinds = [type(h) for h in pipeline.handlers]
        self.assertIn(DiskCaptureHandler, kinds)
        self.assertNotIn(LimsPushHandler, kinds)

    def test_default_includes_lims_push_when_session_present(self):
        args = _parse([
            "-o", "/tmp/out",
            "-u", "http://admin:secret@localhost/senaite",
        ])
        pipeline = build_pipeline(args, _FakeSession())
        kinds = [type(h) for h in pipeline.handlers]
        self.assertIn(LimsPushHandler, kinds)


class ParserTest(unittest.TestCase):

    def test_capture_only_flag_defaults_off(self):
        args = _parse([])
        self.assertFalse(args.capture_only)

    def test_capture_only_flag_sets_true(self):
        args = _parse(["--capture-only"])
        self.assertTrue(args.capture_only)


def test_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(BuildPipelineTest))
    suite.addTests(loader.loadTestsFromTestCase(ParserTest))
    return suite
