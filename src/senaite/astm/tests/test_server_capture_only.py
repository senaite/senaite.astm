# -*- coding: utf-8 -*-
"""Tests for `senaite-astm-server --capture-only`.

The flag turns the server into a hold-and-review pipeline: it
accepts connections, writes captures to disk, and skips the LIMS
push step even when --url is supplied.
"""

import sys
import unittest

from senaite.astm.cli import astm_server
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
        # main() now rejects --capture-only + --url, so this test
        # exercises build_pipeline with the post-validation shape
        # (session=None, capture_only=True).
        args = _parse([
            "-o", "/tmp/out",
            "--capture-only",
        ])
        pipeline = build_pipeline(args, None)
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


class CaptureOnlyConflictTest(unittest.TestCase):
    """--capture-only + --url is a misconfiguration trap: the
    operator probably forgot to drop one of them, and silently
    ignoring --url would mean results never reach the LIMS without
    a single warning. main() must reject the combination."""

    def setUp(self):
        self._saved_argv = sys.argv
        # `main()` calls `_runtime.configure_logging` which attaches
        # handlers to the package logger; snapshot them so we can
        # restore the original list in tearDown and avoid polluting
        # later tests in the same process.
        from senaite.astm import logger as pkg_logger
        self._pkg_logger = pkg_logger
        self._saved_handlers = list(pkg_logger.handlers)

    def tearDown(self):
        sys.argv = self._saved_argv
        self._pkg_logger.handlers = self._saved_handlers

    def test_main_rejects_capture_only_with_url(self):
        sys.argv = [
            "senaite-astm-server",
            "-o", "/tmp/out",
            "-u", "http://admin:secret@localhost/senaite",
            "--capture-only",
        ]
        with self.assertRaises(SystemExit) as ctx:
            astm_server.main()
        # argparse parser.error -> exit code 2
        self.assertEqual(ctx.exception.code, 2)


def test_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(BuildPipelineTest))
    suite.addTests(loader.loadTestsFromTestCase(ParserTest))
    suite.addTests(loader.loadTestsFromTestCase(CaptureOnlyConflictTest))
    return suite
