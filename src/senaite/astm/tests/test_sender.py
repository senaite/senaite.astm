# -*- coding: utf-8 -*-

import io
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from senaite.astm import sender


def make_temp_input(content=b"H|\\^&|\nL|1|N\n"):
    """Write a fixture file and return its path. Caller cleans up."""
    fd, path = tempfile.mkstemp(suffix=".astm")
    with os.fdopen(fd, "wb") as f:
        f.write(content)
    return path


class SenderMainTest(unittest.TestCase):
    """sender.main() parses argv, reads each input file, and pushes the
    aggregated messages to SENAITE iff --url is set.
    """

    def setUp(self):
        self.input_path = make_temp_input()
        self.addCleanup(os.unlink, self.input_path)

    def run_main(self, argv):
        with patch.object(sys, "argv", argv):
            with patch("senaite.astm.sender.post_to_senaite") as post, \
                 patch("senaite.astm.sender.lims.Session") as session_cls:
                sender.main()
        return post, session_cls

    def test_no_url_skips_post(self):
        post, session_cls = self.run_main(
            ["senaite-astm-send", "-i", self.input_path])
        post.assert_not_called()
        session_cls.assert_not_called()

    def test_url_triggers_post(self):
        post, session_cls = self.run_main([
            "senaite-astm-send",
            "-i", self.input_path,
            "-u", "http://admin:admin@senaite.example.com",
        ])
        session_cls.assert_called_once_with(
            "http://admin:admin@senaite.example.com")
        post.assert_called_once()
        messages, session = post.call_args[0]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0], b"H|\\^&|\nL|1|N\n")

    def test_default_session_args(self):
        post, _ = self.run_main([
            "senaite-astm-send",
            "-i", self.input_path,
            "-u", "http://admin:admin@senaite.example.com",
        ])
        kwargs = post.call_args[1]
        self.assertEqual(kwargs["retries"], 3)
        self.assertEqual(kwargs["delay"], 5)
        self.assertEqual(kwargs["consumer"], "senaite.lis2a.import")

    def test_overridden_session_args(self):
        post, _ = self.run_main([
            "senaite-astm-send",
            "-i", self.input_path,
            "-u", "http://admin:admin@senaite.example.com",
            "-r", "10",
            "-d", "1",
            "-c", "custom.consumer",
        ])
        kwargs = post.call_args[1]
        self.assertEqual(kwargs["retries"], 10)
        self.assertEqual(kwargs["delay"], 1)
        self.assertEqual(kwargs["consumer"], "custom.consumer")

    def test_multiple_input_files_aggregate(self):
        second = make_temp_input(b"second\n")
        self.addCleanup(os.unlink, second)
        post, _ = self.run_main([
            "senaite-astm-send",
            "-i", self.input_path, second,
            "-u", "http://admin:admin@senaite.example.com",
        ])
        messages, _ = post.call_args[0]
        self.assertEqual(len(messages), 2)

    def test_help_exits_cleanly(self):
        with patch.object(sys, "argv", ["senaite-astm-send", "--help"]):
            with patch("sys.stdout", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as ctx:
                    sender.main()
                self.assertEqual(ctx.exception.code, 0)
