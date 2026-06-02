# -*- coding: utf-8 -*-
"""Tests for the read-only admin HTTP endpoint."""

import asyncio
import json
import unittest

from senaite.astm.admin import AdminStats
from senaite.astm.admin import render_not_found
from senaite.astm.admin import render_stats_response
from senaite.astm.admin import start_admin_server


class AdminStatsTest(unittest.TestCase):

    def test_initial_snapshot_has_expected_keys(self):
        snap = AdminStats().snapshot()
        self.assertIn("uptime_seconds", snap)
        self.assertIn("active_sessions", snap)
        self.assertIn("frames_dispatched", snap)
        self.assertIn("last_dispatch_at", snap)
        self.assertGreaterEqual(snap["uptime_seconds"], 0)
        self.assertEqual(snap["active_sessions"], 0)
        self.assertEqual(snap["frames_dispatched"], 0)
        self.assertIsNone(snap["last_dispatch_at"])

    def test_session_counters_balance(self):
        stats = AdminStats()
        stats.session_opened()
        stats.session_opened()
        stats.session_closed()
        self.assertEqual(stats.snapshot()["active_sessions"], 1)

    def test_close_never_goes_below_zero(self):
        stats = AdminStats()
        stats.session_closed()
        self.assertEqual(stats.snapshot()["active_sessions"], 0)

    def test_frame_dispatch_increments(self):
        stats = AdminStats()
        stats.frames_in()
        stats.frames_in()
        snap = stats.snapshot()
        self.assertEqual(snap["frames_dispatched"], 2)
        self.assertIsNotNone(snap["last_dispatch_at"])


class RenderResponseTest(unittest.TestCase):

    def test_stats_response_is_valid_http(self):
        stats = AdminStats()
        raw = render_stats_response(stats)
        self.assertTrue(raw.startswith(b"HTTP/1.1 200 OK\r\n"))
        body = raw.split(b"\r\n\r\n", 1)[1]
        snap = json.loads(body.decode("utf-8"))
        self.assertIn("uptime_seconds", snap)

    def test_not_found_response(self):
        raw = render_not_found()
        self.assertTrue(raw.startswith(b"HTTP/1.1 404"))


class AdminServerIntegrationTest(unittest.TestCase):
    """Boot the admin listener on an ephemeral port, hit /stats
    and /missing, confirm the responses."""

    def test_endpoint_roundtrip(self):
        async def run():
            stats = AdminStats()
            stats.session_opened()
            stats.frames_in()
            server = await start_admin_server("127.0.0.1", 0, stats)
            port = server.sockets[0].getsockname()[1]
            try:
                # GET /stats
                reader, writer = await asyncio.open_connection(
                    "127.0.0.1", port)
                writer.write(b"GET /stats HTTP/1.1\r\nHost: x\r\n\r\n")
                await writer.drain()
                response = await reader.read()
                writer.close()
                self.assertIn(b"200 OK", response)
                body = response.split(b"\r\n\r\n", 1)[1]
                payload = json.loads(body.decode("utf-8"))
                self.assertEqual(payload["active_sessions"], 1)
                self.assertEqual(payload["frames_dispatched"], 1)

                # GET /other -> 404
                reader, writer = await asyncio.open_connection(
                    "127.0.0.1", port)
                writer.write(b"GET /other HTTP/1.1\r\n\r\n")
                await writer.drain()
                response = await reader.read()
                writer.close()
                self.assertIn(b"404", response)
            finally:
                server.close()
                await server.wait_closed()

        asyncio.run(run())


def test_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(AdminStatsTest))
    suite.addTests(loader.loadTestsFromTestCase(RenderResponseTest))
    suite.addTests(
        loader.loadTestsFromTestCase(AdminServerIntegrationTest))
    return suite
