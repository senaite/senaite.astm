# -*- coding: utf-8 -*-
"""Tests for `senaite-astm-send --dry-run` and the URL password
masking helper it relies on."""

import io
import logging
import os
import sys
import unittest

from senaite.astm import sender


HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "data")
FIXTURE = os.path.join(DATA_DIR, "yumizen_h500.txt")


class MaskUrlPasswordTest(unittest.TestCase):

    def test_masks_password(self):
        self.assertEqual(
            sender._mask_url_password(
                "http://admin:secret@localhost:8080/senaite"),
            "http://admin:***@localhost:8080/senaite")

    def test_https_masked(self):
        self.assertEqual(
            sender._mask_url_password(
                "https://u:p@host/path"),
            "https://u:***@host/path")

    def test_no_credentials_passes_through(self):
        url = "http://localhost:8080/senaite"
        self.assertEqual(sender._mask_url_password(url), url)

    def test_username_only_passes_through(self):
        # No `:` in the creds portion -> nothing to mask.
        url = "http://justuser@localhost/path"
        self.assertEqual(sender._mask_url_password(url), url)

    def test_empty_or_none(self):
        self.assertEqual(sender._mask_url_password(""), "")
        self.assertEqual(sender._mask_url_password(None), "")


class _CaptureHandler(logging.Handler):
    """Capture log records into a list for assertion."""

    def __init__(self):
        super(_CaptureHandler, self).__init__()
        self.records = []

    def emit(self, record):
        self.records.append(self.format(record))


class DryRunCliTest(unittest.TestCase):
    """Run the CLI in-process with `--dry-run` and confirm the
    password is masked, the LIMS is not contacted, and the
    summary line lists each message size."""

    def setUp(self):
        self.handler = _CaptureHandler()
        self.handler.setLevel(logging.INFO)
        sender.logger.addHandler(self.handler)
        sender.logger.setLevel(logging.INFO)
        self._saved_argv = sys.argv

    def tearDown(self):
        sender.logger.removeHandler(self.handler)
        sys.argv = self._saved_argv

    def test_dry_run_does_not_call_post_to_senaite(self):
        called = {"hit": False}

        def fake_post(*a, **kw):
            called["hit"] = True

        original = sender.post_to_senaite
        sender.post_to_senaite = fake_post
        try:
            sys.argv = [
                "senaite-astm-send",
                "-i", FIXTURE,
                "-u", "http://admin:secret@localhost/senaite",
                "--dry-run",
            ]
            sender.main()
        finally:
            sender.post_to_senaite = original

        self.assertFalse(called["hit"])
        output = "\n".join(self.handler.records)
        self.assertIn("DRY RUN", output)
        self.assertIn("admin:***", output)
        self.assertNotIn("secret", output)
        self.assertIn("messages: 1", output)


def test_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(MaskUrlPasswordTest))
    suite.addTests(loader.loadTestsFromTestCase(DryRunCliTest))
    return suite
