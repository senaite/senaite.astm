# -*- coding: utf-8 -*-
"""``senaite-astm-server`` CLI entry point.

Wires the slim ASTM transport (``transports/astm/protocol.py``) to
the message :class:`Pipeline`. The transport emits complete frame
batches; this module wraps them into an :class:`Envelope`, dispatches
the pipeline as a tracked task, and waits for in-flight work on
shutdown.

Lifecycle helpers (logging, signal handlers, task draining) live in
:mod:`senaite.astm.cli._runtime` and are shared with the HL7 CLI.
"""

import argparse
import asyncio
import os

from senaite.astm import logger
from senaite.astm.admin import AdminStats
from senaite.astm.admin import start_admin_server
from senaite.astm.cli import _runtime
from senaite.astm.core.lims import LimsPushHandler
from senaite.astm.core.output import DiskCaptureHandler
from senaite.astm.core.pipeline import Pipeline
from senaite.astm.transports.astm.protocol import ASTMProtocol
from senaite.astm.wrapper import Wrapper

LOGFILE = "senaite-astm-server.log"


def build_arg_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    astm_group = parser.add_argument_group("ASTM SERVER")
    astm_group.add_argument(
        "-l", "--listen", type=str, default="0.0.0.0",
        help="Listen IP address")
    astm_group.add_argument(
        "-p", "--port", type=str, default="4010",
        help="Port to connect")
    astm_group.add_argument(
        "-o", "--output", type=str,
        help="Output directory to write full messages")
    astm_group.add_argument(
        "--admin-port", type=int, default=None,
        help="Open a read-only HTTP admin endpoint on this port "
             "(GET /stats returns JSON: uptime, active sessions, "
             "frames dispatched). Off by default. The admin "
             "listener binds to --admin-listen; set that to a "
             "non-public interface — no authentication is "
             "performed.")

    astm_group.add_argument(
        "--admin-listen", type=str, default="127.0.0.1",
        help="Bind address for the --admin-port endpoint.")

    astm_group.add_argument(
        "--capture-only", action="store_true",
        help="Accept connections and persist captures, but skip "
             "the LIMS push step even when --url is given. Useful "
             "for a hold-and-review workflow where an operator (or "
             "a UI on top of this server) wants to inspect messages "
             "before they propagate to the LIMS. Requires --output.")

    astm_group.add_argument(
        "--shutdown-grace-seconds", type=int,
        default=_runtime.DEFAULT_SHUTDOWN_GRACE_SECONDS,
        help="Seconds to wait for in-flight handler tasks to "
             "finish before forcefully cancelling them on shutdown.")

    _runtime.add_lims_arg_group(
        parser, default_consumer="senaite.core.lis2a.import")

    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose logging")
    parser.add_argument(
        "--logfile", default=LOGFILE,
        help="Path to store log files")

    return parser


def build_pipeline(args, session):
    handlers = []
    if args.output:
        handlers.append(DiskCaptureHandler(os.path.abspath(args.output)))
    if session is not None and not getattr(args, "capture_only", False):
        handlers.append(LimsPushHandler(
            session,
            retries=args.retries,
            delay=args.delay,
            consumer=args.consumer,
            message_format=args.message_format,
        ))
    return Pipeline(handlers)


def make_frame_callback(loop, pipeline, task_set, stats=None):
    """ASTM-specific frame callback.

    The ASTM transport hands us a *list of frames* per session; we
    wrap them into an :class:`Envelope` before running the pipeline.
    When `stats` is supplied the wrapper bumps `frames_in()` for
    every batch the transport delivers, so the admin /stats
    endpoint reports a live dispatch counter.
    """
    inner = _runtime.make_frame_callback(
        loop, pipeline, task_set,
        to_envelope=lambda frames: Wrapper(frames).to_envelope())
    if stats is None:
        return inner

    def _wrapped(client, frames):
        stats.frames_in()
        return inner(client, frames)

    return _wrapped


async def amain(args, stop_event=None):
    """Async entry point.

    Boots the listener, installs signal handlers, and blocks until a
    shutdown signal arrives.

    :param stop_event: Optional pre-created :class:`asyncio.Event`
        used to request shutdown. Tests can drive shutdown via this
        event without going through OS signals.
    """
    loop = asyncio.get_running_loop()
    task_set = set()
    pipeline = build_pipeline(args, args.session)

    stats = AdminStats() if getattr(args, "admin_port", None) else None
    frame_callback = make_frame_callback(
        loop, pipeline, task_set, stats=stats)

    server = await loop.create_server(
        lambda: ASTMProtocol(
            frame_callback=frame_callback, stats=stats),
        host=args.listen, port=args.port)

    for socket in server.sockets:
        ip, port = socket.getsockname()
        logger.info("Starting server on {}:{}".format(ip, port))
    logger.info("ASTM server ready to handle connections ...")

    admin_server = None
    if stats is not None:
        admin_server = await start_admin_server(
            args.admin_listen, args.admin_port, stats)

    if stop_event is None:
        stop_event = asyncio.Event()
    _runtime.install_shutdown_handlers(loop, stop_event)

    try:
        await stop_event.wait()
    finally:
        logger.info("Shutting down server...")
        if admin_server is not None:
            admin_server.close()
            await admin_server.wait_closed()
        server.close()
        await server.wait_closed()
        await _runtime.drain_tasks(task_set, args.shutdown_grace_seconds)
        logger.info("Server is now down...")


# Backwards compatibility for the lifecycle tests that import the
# pre-extraction helper names directly.
LOGFILE_MAX_BYTES = _runtime.LOGFILE_MAX_BYTES
LOGFILE_BACKUP_COUNT = _runtime.LOGFILE_BACKUP_COUNT
DEFAULT_SHUTDOWN_GRACE_SECONDS = _runtime.DEFAULT_SHUTDOWN_GRACE_SECONDS
configure_logging = _runtime.configure_logging
validate_output = _runtime.validate_output
validate_lims = _runtime.validate_lims
_drain_tasks = _runtime.drain_tasks


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    _runtime.configure_logging(args)
    if args.capture_only and not args.output:
        parser.error("--capture-only requires --output")
    if args.capture_only and args.url:
        # The modes are conceptually mutually exclusive: capture-
        # only persists captures and stops there, --url tells the
        # pipeline where to forward them. Letting them coexist
        # silently means a misconfigured systemd unit (e.g. left
        # --url in the line after adding --capture-only) ships
        # with both flags and the operator never notices results
        # aren't reaching the LIMS until somebody investigates.
        parser.error(
            "--capture-only is mutually exclusive with --url; "
            "either drop --url to confirm capture-only, or drop "
            "--capture-only to forward to the LIMS.")
    _runtime.validate_output(args.output)
    if args.capture_only:
        logger.info(
            "Capture-only mode: LIMS push disabled; "
            "captures persisted to %s", args.output)
        args.session = None
    else:
        args.session = _runtime.validate_lims(args.url)

    try:
        asyncio.run(amain(args))
    except KeyboardInterrupt:
        logger.info("Interrupted; exiting.")


if __name__ == "__main__":
    main()
