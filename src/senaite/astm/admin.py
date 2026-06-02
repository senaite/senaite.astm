# -*- coding: utf-8 -*-
"""Read-only admin HTTP endpoint for senaite-astm-server.

A tiny asyncio TCP server that answers `GET /stats` with a JSON
snapshot of the server's runtime counters: uptime, active session
count, frame batches dispatched. A UI on top of senaite.astm can
poll this without screen-scraping the log file.

Intentionally bare:

- No external deps. The HTTP response is hand-rolled HTTP/1.1.
- No authentication. Bind to localhost or an internal interface.
- No routes other than `/stats`. Everything else returns 404.

Stats are tracked in a single shared :class:`AdminStats` instance
the server hands to both the pipeline (via callbacks) and the
admin protocol.
"""

import json
import time

from senaite.astm import logger


class AdminStats(object):
    """Mutable counter bag the server updates and the admin
    endpoint reads. Plain attributes — no locks; asyncio is
    single-threaded."""

    def __init__(self):
        self.started_at = time.time()
        self.active_sessions = 0
        self.frames_dispatched = 0
        self.last_dispatch_at = None

    def session_opened(self):
        self.active_sessions += 1

    def session_closed(self):
        if self.active_sessions > 0:
            self.active_sessions -= 1

    def frames_in(self):
        self.frames_dispatched += 1
        self.last_dispatch_at = time.time()

    def snapshot(self):
        now = time.time()
        return {
            "uptime_seconds": round(now - self.started_at, 3),
            "active_sessions": self.active_sessions,
            "frames_dispatched": self.frames_dispatched,
            "last_dispatch_at": self.last_dispatch_at,
        }


def render_stats_response(stats):
    """Hand-rolled HTTP/1.1 response for `GET /stats`. Returns
    bytes; the caller writes them on the connection and closes."""
    body = json.dumps(stats.snapshot()).encode("utf-8")
    headers = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n"
        "\r\n"
    ) % len(body)
    return headers.encode("utf-8") + body


def render_not_found():
    body = b"not found\n"
    headers = (
        "HTTP/1.1 404 Not Found\r\n"
        "Content-Type: text/plain\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n"
        "\r\n"
    ) % len(body)
    return headers.encode("utf-8") + body


async def _handle(reader, writer, stats):
    """Handle one admin HTTP request. Reads only the request line;
    ignores headers. Returns either the stats JSON or 404."""
    try:
        request_line = await reader.readline()
    except Exception:
        writer.close()
        return
    parts = request_line.split()
    if len(parts) >= 2 and parts[0] == b"GET" and parts[1] == b"/stats":
        writer.write(render_stats_response(stats))
    else:
        writer.write(render_not_found())
    try:
        await writer.drain()
    except Exception:
        pass
    writer.close()


async def start_admin_server(host, port, stats):
    """Open the admin listener and return the asyncio Server.

    The caller is expected to close the server on shutdown
    (`server.close()` + `await server.wait_closed()`).
    """
    import asyncio

    server = await asyncio.start_server(
        lambda r, w: _handle(r, w, stats),
        host=host, port=port)
    for sock in server.sockets:
        ip, port = sock.getsockname()[:2]
        logger.info("Admin endpoint on http://%s:%s/stats", ip, port)
    return server
