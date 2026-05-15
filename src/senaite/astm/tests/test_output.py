# -*- coding: utf-8 -*-
"""Tests for :class:`senaite.astm.core.output.DiskCaptureHandler`.

PR-H promoted disk capture from an implicit ``protocol.log_message``
side effect (rooted at ``$CWD/astm_messages``) to a first-class
pipeline handler. The contract under test:

- ``path=None`` / empty path makes the handler a no-op (used by the
  CLI when ``--output`` is not supplied).
- A normal call writes one file containing the raw ASTM payload.
- The target directory is created on first write if it does not
  already exist.
"""

import asyncio
import os
import tempfile
import unittest

from senaite.astm.core.envelope import Envelope, Metadata
from senaite.astm.core.output import DiskCaptureHandler


def make_envelope(astm="raw-astm-bytes"):
    return Envelope(metadata=Metadata(astm=astm, lis2a="lis"))


class DiskCaptureHandlerTest(unittest.IsolatedAsyncioTestCase):

    async def test_noop_when_path_is_none(self):
        handler = DiskCaptureHandler(path=None)
        # Must not raise and must not create any file anywhere.
        await handler(make_envelope())

    async def test_noop_when_path_is_empty_string(self):
        handler = DiskCaptureHandler(path="")
        await handler(make_envelope())

    async def test_writes_one_file_per_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            handler = DiskCaptureHandler(path=tmp)
            await handler(make_envelope("session-one"))
            # The timestamp-derived filename has 1-second resolution,
            # so back-to-back writes can collide and overwrite. Wait
            # past the boundary before the second write.
            await asyncio.sleep(1.05)
            await handler(make_envelope("session-two"))

            files = sorted(os.listdir(tmp))
            self.assertEqual(len(files), 2)

            # Files contain the raw ASTM payload, not the JSON envelope.
            contents = []
            for name in files:
                with open(os.path.join(tmp, name), "rb") as fh:
                    contents.append(fh.read())
            self.assertIn(b"session-one", contents[0] + contents[1])
            self.assertIn(b"session-two", contents[0] + contents[1])

    async def test_creates_target_directory_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "does", "not", "exist")
            self.assertFalse(os.path.exists(target))

            handler = DiskCaptureHandler(path=target)
            await handler(make_envelope())

            self.assertTrue(os.path.isdir(target))
            self.assertEqual(len(os.listdir(target)), 1)

    async def test_handler_exposes_name_for_pipeline_logging(self):
        # The pipeline uses ``handler.name`` in its error reports.
        self.assertEqual(DiskCaptureHandler(path="/tmp").name, "disk_capture")


class CLIBuildPipelineTest(unittest.TestCase):
    """``cli.astm_server.build_pipeline`` no longer auto-discovers
    capture targets. The implicit ``$CWD/astm_messages/`` magic is
    gone."""

    def test_no_output_means_no_capture_handler(self):
        from senaite.astm.cli import astm_server

        class _Args(object):
            output = None
            retries = 1
            delay = 0
            consumer = "x"
            message_format = "json"

        # Even if the legacy magic directory existed in CWD, no
        # capture handler must be added when --output is absent.
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "astm_messages"))
            cwd = os.getcwd()
            try:
                os.chdir(tmp)
                pipeline = astm_server.build_pipeline(_Args(), session=None)
            finally:
                os.chdir(cwd)
            self.assertEqual(len(pipeline), 0)

    def test_explicit_output_adds_capture_handler(self):
        from senaite.astm.cli import astm_server

        with tempfile.TemporaryDirectory() as tmp:
            class _Args(object):
                output = tmp
                retries = 1
                delay = 0
                consumer = "x"
                message_format = "json"

            pipeline = astm_server.build_pipeline(_Args(), session=None)
            self.assertEqual(len(pipeline), 1)
            self.assertEqual(pipeline.handlers[0].name, "disk_capture")


if __name__ == "__main__":
    unittest.main()
