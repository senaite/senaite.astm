# -*- coding: utf-8 -*-
"""``senaite-astm-server`` CLI entry point.

Wires the slim ASTM transport (``transports/astm/protocol.py``) to
the message :class:`Pipeline`. The transport emits complete frame
batches; this module wraps them into an :class:`Envelope`, dispatches
the pipeline as a tracked task, and waits for in-flight work on
shutdown.

The CLI surface (arguments, default ports, logfile name) is
preserved from the previous ``senaite.astm.server`` module.
"""

import argparse
import asyncio
import logging
import logging.handlers
import os
import signal
import sys

from senaite.astm import logger
from senaite.astm.core import lims
from senaite.astm.core.handlers import DiskCaptureHandler
from senaite.astm.core.handlers import LimsPushHandler
from senaite.astm.core.handlers import default_disk_capture_path
from senaite.astm.core.pipeline import Pipeline
from senaite.astm.transports.astm.protocol import ASTMProtocol
from senaite.astm.wrapper import Wrapper

LOGFILE = "senaite-astm-server.log"
LOGFILE_MAX_BYTES = 10 * 1024 * 1024
LOGFILE_BACKUP_COUNT = 5
DEFAULT_SHUTDOWN_GRACE_SECONDS = 30


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
        default=DEFAULT_SHUTDOWN_GRACE_SECONDS,
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


def configure_logging(args):
    if args.logfile:
        handler = logging.handlers.RotatingFileHandler(
            args.logfile,
            maxBytes=LOGFILE_MAX_BYTES,
            backupCount=LOGFILE_BACKUP_COUNT)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-8s %(message)s"))
        logger.addHandler(handler)

    logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    logger.addHandler(logging.StreamHandler())


def validate_output(output):
    if output and not os.path.isdir(output):
        logger.error("Output path must be an existing directory")
        sys.exit(-1)


def validate_lims(url):
    if not url:
        return None
    session = lims.Session(url)
    logger.info("Checking connection to SENAITE ...")
    try:
        session.auth()
    except lims.SenaiteError as exc:
        logger.error("Could not connect to SENAITE: {}".format(exc))
        sys.exit(-1)
    return session


def build_pipeline(args, session):
    handlers = []
    output_path = args.output or default_disk_capture_path()
    if output_path:
        handlers.append(DiskCaptureHandler(os.path.abspath(output_path)))
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
    """Return a frame callback that dispatches a tracked pipeline run.

    The protocol invokes the callback synchronously from the loop
    thread (inside ``data_received``). We schedule the wrap + pipeline
    work as a task so the protocol can return immediately, and we
    register that task into ``task_set`` so shutdown can wait for it.
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


async def _drain_tasks(task_set, grace_seconds):
    """Await all in-flight tasks up to ``grace_seconds``.

    Tasks still running after the grace period are cancelled.
    """
    if not task_set:
        return
    logger.info(
        "Waiting up to %ds for %d in-flight task(s) to finish...",
        grace_seconds, len(task_set))
    pending = list(task_set)
    done, still_pending = await asyncio.wait(
        pending, timeout=grace_seconds)
    if still_pending:
        logger.warning(
            "Cancelling %d task(s) that did not finish within "
            "the %ds grace period",
            len(still_pending), grace_seconds)
        for task in still_pending:
            task.cancel()
        await asyncio.gather(*still_pending, return_exceptions=True)


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

    def request_shutdown(sig_name):
        if stop_event.is_set():
            return
        logger.info("Received %s, initiating graceful shutdown", sig_name)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                sig, request_shutdown, sig.name)
        except (NotImplementedError, RuntimeError):
            # Windows or non-main-thread loops can't install loop-level
            # signal handlers. Fall back to default behaviour; callers
            # that need programmatic shutdown can pass ``stop_event``.
            pass

    try:
        await stop_event.wait()
    finally:
        logger.info("Shutting down server...")
        server.close()
        await server.wait_closed()
        await _drain_tasks(task_set, args.shutdown_grace_seconds)
        logger.info("Server is now down...")


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    configure_logging(args)
    validate_output(args.output)
    args.session = validate_lims(args.url)

    try:
        asyncio.run(amain(args))
    except KeyboardInterrupt:
        # Reach this only on platforms where the loop's signal handler
        # is unavailable (Windows). The graceful path runs via
        # ``request_shutdown``.
        logger.info("Interrupted; exiting.")


if __name__ == "__main__":
    main()
