# -*- coding: utf-8 -*-
"""Tests for the hardened CLI server lifecycle.

PR-G replaced the legacy ``server.main`` with an async ``amain``
that:

- writes its logfile via a sane :class:`RotatingFileHandler` (10 MB
  per file, 5 backups) instead of rotating after every record;
- tracks every pipeline-run task it dispatches so shutdown can
  ``await`` in-flight work;
- waits up to ``--shutdown-grace-seconds`` for those tasks before
  cancelling them.

The tests below cover those guarantees without orchestrating a real
SIGTERM (which is fiddly under ``pytest``): they exercise
``_drain_tasks``, ``make_frame_callback`` and the logging setup
directly.
"""

import asyncio
import logging
import logging.handlers
import os
import tempfile
import unittest

from senaite.astm import logger
from senaite.astm.cli import astm_server


class _Args(object):
    """Minimal stand-in for the argparse Namespace."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


class LogRotationTest(unittest.TestCase):

    def test_constants_are_sane(self):
        # 5-byte rotation was a real bug in the legacy server.
        self.assertGreaterEqual(astm_server.LOGFILE_MAX_BYTES, 1024 * 1024)
        self.assertGreaterEqual(astm_server.LOGFILE_BACKUP_COUNT, 1)

    def test_configure_logging_does_not_rotate_per_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            logfile = os.path.join(tmp, "server.log")
            args = _Args(logfile=logfile, verbose=False)

            # Snapshot existing handlers so we can detach what we add.
            before = list(logger.handlers)
            try:
                astm_server.configure_logging(args)
                # Find the rotating handler we just attached.
                rotating = [h for h in logger.handlers
                            if isinstance(
                                h, logging.handlers.RotatingFileHandler)]
                self.assertEqual(len(rotating), 1)
                handler = rotating[0]
                self.assertEqual(
                    handler.maxBytes, astm_server.LOGFILE_MAX_BYTES)
                self.assertEqual(
                    handler.backupCount,
                    astm_server.LOGFILE_BACKUP_COUNT)

                # Emit a few records — none should rotate.
                for _ in range(20):
                    logger.info("a log line that easily exceeds 5 bytes")
                handler.flush()

                rotated = [
                    name for name in os.listdir(tmp)
                    if name.startswith("server.log.")
                ]
                self.assertEqual(rotated, [])
            finally:
                # Restore the logger to its pre-test state so other
                # tests are not noisy.
                for h in list(logger.handlers):
                    if h not in before:
                        logger.removeHandler(h)


class DrainTasksTest(unittest.IsolatedAsyncioTestCase):

    async def test_returns_immediately_when_empty(self):
        await astm_server._drain_tasks(set(), grace_seconds=5)

    async def test_waits_for_inflight_task(self):
        completed = []

        async def slow():
            await asyncio.sleep(0.05)
            completed.append(True)

        task = asyncio.create_task(slow())
        await astm_server._drain_tasks({task}, grace_seconds=2)
        self.assertEqual(completed, [True])
        self.assertTrue(task.done())

    async def test_cancels_tasks_that_exceed_grace(self):
        async def stuck():
            await asyncio.sleep(60)

        task = asyncio.create_task(stuck())
        await astm_server._drain_tasks({task}, grace_seconds=0.05)
        self.assertTrue(task.cancelled())


class FrameCallbackTest(unittest.IsolatedAsyncioTestCase):

    async def test_callback_runs_pipeline_against_wrapped_envelope(self):
        seen_envelopes = []

        async def capture_handler(envelope):
            seen_envelopes.append(envelope)

        from senaite.astm.core.pipeline import Pipeline

        pipeline = Pipeline([capture_handler])
        loop = asyncio.get_running_loop()
        task_set = set()
        callback = astm_server.make_frame_callback(
            loop, pipeline, task_set)

        frames = [
            b"\x021H|\\^&|||C111^Roche^c111^4.2.2.1730^1^13147|||||"
            b"host|RSUPL^REAL|P|1|20230727162028\r\x179B\r\n",
            b"\x027L|1|N\r\x030A\r\n",
        ]
        callback("127.0.0.1:11111", frames)

        # Task must be tracked synchronously so shutdown can wait
        self.assertEqual(len(task_set), 1)

        # Drain via the production helper to prove the contract holds.
        await astm_server._drain_tasks(task_set, grace_seconds=2)

        self.assertEqual(len(seen_envelopes), 1)
        self.assertEqual(len(seen_envelopes[0].H), 1)
        self.assertEqual(task_set, set())

    async def test_wrap_failure_does_not_crash_dispatch(self):
        called = []

        async def handler(envelope):
            called.append(envelope)

        from senaite.astm.core.pipeline import Pipeline

        pipeline = Pipeline([handler])
        loop = asyncio.get_running_loop()
        task_set = set()
        callback = astm_server.make_frame_callback(
            loop, pipeline, task_set)

        # Garbage frames that will not parse.
        callback("127.0.0.1:11111", [b"not-a-frame"])
        await astm_server._drain_tasks(task_set, grace_seconds=2)

        self.assertEqual(called, [])


class GracefulShutdownTest(unittest.IsolatedAsyncioTestCase):
    """Boot the server, dispatch a slow in-flight task, request
    shutdown, and assert the task ran to completion before
    ``amain`` returned."""

    PORT = 7984

    async def test_inflight_task_completes_before_amain_returns(self):
        completed = asyncio.Event()
        observed_during_shutdown = []

        async def slow_handler(envelope):
            # Sleep across the shutdown moment to prove drain waits.
            await asyncio.sleep(0.2)
            completed.set()
            observed_during_shutdown.append(True)

        # Patch the pipeline builder so we don't need a live LIMS.
        from senaite.astm.core.pipeline import Pipeline

        original_build = astm_server.build_pipeline
        astm_server.build_pipeline = lambda args, session: Pipeline(
            [slow_handler])
        try:
            args = _Args(
                listen="127.0.0.1",
                port=self.PORT,
                output=None,
                url=None,
                session=None,
                shutdown_grace_seconds=5,
                consumer="x",
                message_format="json",
                retries=1,
                delay=0,
            )

            stop_event = asyncio.Event()
            server_task = asyncio.create_task(
                astm_server.amain(args, stop_event=stop_event))

            # Give the server a moment to start listening.
            await asyncio.sleep(0.05)

            # Send one full ASTM session to trigger the slow handler.
            from senaite.astm.constants import ACK, ENQ, EOT
            reader, writer = await asyncio.open_connection(
                "127.0.0.1", self.PORT)
            writer.write(ENQ)
            await writer.drain()
            self.assertEqual(await reader.read(100), ACK)
            # Single non-chunked terminator frame — enough to put the
            # protocol's EOT into "has messages" mode. ETX (\x03)
            # rather than ETB (\x17) keeps it out of chunked mode.
            frame = b"\x021L|1|N\r\x0304\r\n"
            writer.write(frame)
            await writer.drain()
            self.assertEqual(await reader.read(100), ACK)
            writer.write(EOT)
            await writer.drain()
            writer.close()
            await writer.wait_closed()

            # Wait until the slow handler is in-flight, then request
            # graceful shutdown via the test-injected stop event.
            await asyncio.sleep(0.05)
            stop_event.set()

            await asyncio.wait_for(server_task, timeout=5)
            self.assertTrue(completed.is_set())
            self.assertEqual(observed_during_shutdown, [True])
        finally:
            astm_server.build_pipeline = original_build


if __name__ == "__main__":
    unittest.main()
