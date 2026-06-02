# -*- coding: utf-8 -*-
"""Tests for the wiring between ASTMProtocol / the frame-callback
and the AdminStats counter bag exposed at /stats.

Pre-production review flagged that AdminStats() was instantiated
but never updated, so /stats perpetually reported zeros. These
tests guard the wiring: a session opening and closing must bump
the counters; a frame batch handed to the wrapped frame_callback
must increment frames_dispatched.
"""

import asyncio
import unittest
from unittest.mock import MagicMock

from senaite.astm.admin import AdminStats
from senaite.astm.cli.astm_server import make_frame_callback
from senaite.astm.transports.astm.protocol import ASTMProtocol


class ProtocolSessionWiringTest(unittest.TestCase):

    def _fake_transport(self, peer=("1.2.3.4", 9999)):
        transport = MagicMock()
        transport.get_extra_info.return_value = peer
        return transport

    def test_connection_made_bumps_active_sessions(self):
        stats = AdminStats()
        proto = ASTMProtocol(stats=stats)
        asyncio.run(self._made(proto))
        self.assertEqual(
            stats.snapshot()["active_sessions"], 1)

    async def _made(self, proto):
        proto.connection_made(self._fake_transport())

    def test_connection_lost_balances_session_count(self):
        stats = AdminStats()
        proto = ASTMProtocol(stats=stats)
        asyncio.run(self._made_then_lost(proto))
        self.assertEqual(
            stats.snapshot()["active_sessions"], 0)

    async def _made_then_lost(self, proto):
        proto.connection_made(self._fake_transport())
        proto.connection_lost(None)

    def test_no_stats_is_a_no_op(self):
        proto = ASTMProtocol()
        # connection_made / connection_lost must not raise when
        # stats is None — older callers don't pass it.
        asyncio.run(self._made_then_lost(proto))


class FrameCallbackWiringTest(unittest.TestCase):

    def test_wrapped_callback_increments_frames_dispatched(self):
        loop = asyncio.new_event_loop()
        try:
            stats = AdminStats()
            pipeline = MagicMock()
            pipeline.run = MagicMock()
            task_set = set()

            cb = make_frame_callback(
                loop, pipeline, task_set, stats=stats)
            # The wrapped callback is sync — calling it must bump
            # frames_in. We don't care that the inner callback
            # schedules a task; only that the counter ticked.
            cb("client-1", [b"\x021H|\\^&|\x03B7"])

            self.assertEqual(
                stats.snapshot()["frames_dispatched"], 1)
            self.assertIsNotNone(
                stats.snapshot()["last_dispatch_at"])
        finally:
            loop.close()

    def test_no_stats_returns_inner_callback_unwrapped(self):
        loop = asyncio.new_event_loop()
        try:
            pipeline = MagicMock()
            task_set = set()
            cb = make_frame_callback(
                loop, pipeline, task_set, stats=None)
            # No exception means the unwrapped path works.
            cb("client-1", [b"\x021H|\\^&|\x03B7"])
        finally:
            loop.close()


def test_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(
        loader.loadTestsFromTestCase(ProtocolSessionWiringTest))
    suite.addTests(
        loader.loadTestsFromTestCase(FrameCallbackWiringTest))
    return suite
