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
from senaite.astm.cli import _runtime
from senaite.astm.core import lims
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
    lims_group = parser.add_argument_group("SENAITE LIMS")

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
        "--shutdown-grace-seconds", type=int,
        default=_runtime.DEFAULT_SHUTDOWN_GRACE_SECONDS,
        help="Seconds to wait for in-flight handler tasks to "
             "finish before forcefully cancelling them on shutdown.")

    lims_group.add_argument(
        "-u", "--url", type=str,
        help="SENAITE URL address including username and password in "
             "the format: http(s)://<user>:<password>@<senaite_url>")
    lims_group.add_argument(
        "-c", "--consumer", type=str,
        default="senaite.core.lis2a.import",
        help="SENAITE push consumer interface")
    lims_group.add_argument(
        "-m", "--message-format", type=str, default="json",
        help="Message format to send to SENAITE. "
             "Allowed formats: 'astm', 'lis2a', 'json'.")
    lims_group.add_argument(
        "-r", "--retries", type=int, default=3,
        help="Number of attempts of reconnection when SENAITE "
             "instance is not reachable. Only has effect when "
             "argument --url is set")
    lims_group.add_argument(
        "-d", "--delay", type=int, default=5,
        help="Time delay in seconds between retries when SENAITE "
             "instance is not reachable. Only has effect when "
             "argument --url is set")

    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose logging")
    parser.add_argument(
        "--logfile", default=LOGFILE,
        help="Path to store log files")

    return parser


def validate_lims(url):
    if not url:
        return None
    session = lims.Session(url)
    logger.info("Checking connection to SENAITE ...")
    try:
        session.auth()
    except lims.SenaiteError as exc:
        logger.error("Could not connect to SENAITE: {}".format(exc))
        raise SystemExit(-1)
    return session


def build_pipeline(args, session):
    handlers = []
    if args.output:
        handlers.append(DiskCaptureHandler(os.path.abspath(args.output)))
    if session is not None:
        handlers.append(LimsPushHandler(
            session,
            retries=args.retries,
            delay=args.delay,
            consumer=args.consumer,
            message_format=args.message_format,
        ))
    return Pipeline(handlers)


def make_frame_callback(loop, pipeline, task_set):
    """ASTM-specific frame callback.

    The ASTM transport hands us a *list of frames* per session; we
    wrap them into an :class:`Envelope` before running the pipeline.
    """
    def frame_callback(client, frames):
        task = loop.create_task(
            _process_frames(client, frames, pipeline))
        task_set.add(task)
        task.add_done_callback(task_set.discard)
    return frame_callback


async def _process_frames(client, frames, pipeline):
    try:
        envelope = Wrapper(frames).to_envelope()
    except Exception as exc:
        logger.error(
            "Failed to wrap %d frames from %s: %r",
            len(frames), client, exc)
        return
    await pipeline.run(envelope)


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
    frame_callback = make_frame_callback(loop, pipeline, task_set)

    server = await loop.create_server(
        lambda: ASTMProtocol(frame_callback=frame_callback),
        host=args.listen, port=args.port)

    for socket in server.sockets:
        ip, port = socket.getsockname()
        logger.info("Starting server on {}:{}".format(ip, port))
    logger.info("ASTM server ready to handle connections ...")

    if stop_event is None:
        stop_event = asyncio.Event()
    _runtime.install_shutdown_handlers(loop, stop_event)

    try:
        await stop_event.wait()
    finally:
        logger.info("Shutting down server...")
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
_drain_tasks = _runtime.drain_tasks


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    _runtime.configure_logging(args)
    _runtime.validate_output(args.output)
    args.session = validate_lims(args.url)

    try:
        asyncio.run(amain(args))
    except KeyboardInterrupt:
        logger.info("Interrupted; exiting.")


if __name__ == "__main__":
    main()
