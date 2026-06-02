# -*- coding: utf-8 -*-
"""Shared CLI runtime helpers for the senaite.astm transport servers.

The ASTM and HL7 CLI servers both:

- attach a sane RotatingFileHandler to the package logger;
- validate that ``--output`` (when provided) points at an existing
  directory;
- install loop-level SIGINT / SIGTERM handlers that flip a shared
  ``asyncio.Event``;
- await in-flight pipeline tasks up to a configurable grace period
  before forcefully cancelling them on shutdown.

Keeping those bits here means each transport's ``cli/<name>_server.py``
focuses on its own wiring (protocol class, frame-callback, pipeline
shape) instead of re-implementing the lifecycle dance.
"""

import asyncio
import logging
import logging.handlers
import os
import signal
import sys

from senaite.astm import logger
from senaite.astm.core import lims

LOGFILE_MAX_BYTES = 10 * 1024 * 1024
LOGFILE_BACKUP_COUNT = 5
DEFAULT_SHUTDOWN_GRACE_SECONDS = 30


def configure_logging(args):
    """Attach the rotating logfile + stream handlers to the package
    logger and set the verbosity from ``args.verbose``.

    Idempotent: a StreamHandler is added only if the logger has
    none already, and the rotating file handler is added only when
    no existing handler points at the same file. Without these
    guards a test suite that invokes the CLI repeatedly piles up
    duplicate handlers and prints every log line N times."""
    if getattr(args, "logfile", None):
        already_pointed_at_file = any(
            isinstance(h, logging.handlers.RotatingFileHandler)
            and h.baseFilename == os.path.abspath(args.logfile)
            for h in logger.handlers)
        if not already_pointed_at_file:
            handler = logging.handlers.RotatingFileHandler(
                args.logfile,
                maxBytes=LOGFILE_MAX_BYTES,
                backupCount=LOGFILE_BACKUP_COUNT)
            handler.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)-8s %(message)s"))
            logger.addHandler(handler)

    logger.setLevel(
        logging.DEBUG if getattr(args, "verbose", False) else logging.INFO)
    if not any(isinstance(h, logging.StreamHandler)
               and not isinstance(h, logging.FileHandler)
               for h in logger.handlers):
        logger.addHandler(logging.StreamHandler())


def validate_output(output):
    """Exit with an error if ``output`` is set but not a directory.

    Uses ``sys.exit(1)`` rather than ``sys.exit(-1)``: on POSIX the
    negative value is sign-flipped to 255 by the C runtime, which
    some monitoring tools interpret as "killed by signal" rather
    than "exited cleanly with an error".
    """
    if output and not os.path.isdir(output):
        logger.error("Output path must be an existing directory")
        sys.exit(1)


def install_shutdown_handlers(loop, stop_event):
    """Wire SIGINT / SIGTERM to ``stop_event``.

    Platforms where loop-level signal handlers are unsupported
    (Windows, non-main-thread loops) silently fall back to the
    default behaviour; callers that need programmatic shutdown
    must drive ``stop_event`` directly.
    """
    def request_shutdown(sig_name):
        if stop_event.is_set():
            return
        logger.info(
            "Received %s, initiating graceful shutdown", sig_name)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                sig, request_shutdown, sig.name)
        except (NotImplementedError, RuntimeError):
            pass


async def drain_tasks(task_set, grace_seconds):
    """Await every task in ``task_set`` up to ``grace_seconds``.

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


def make_tracked_dispatcher(loop, pipeline, task_set):
    """Build a frame-callback that schedules ``pipeline.run(payload)``
    as a tracked task on ``loop``.

    Transports invoke the returned callable synchronously from the
    loop thread; the heavy work happens off the protocol's
    ``data_received`` path so the next frame can be read immediately.
    """
    def dispatch(client, payload):
        task = loop.create_task(_run(payload, pipeline))
        task_set.add(task)
        task.add_done_callback(task_set.discard)
    return dispatch


async def _run(payload, pipeline):
    try:
        await pipeline.run(payload)
    except Exception as exc:
        logger.error("Pipeline run failed: %r", exc)


def make_frame_callback(loop, pipeline, task_set, to_envelope):
    """Build a transport-agnostic frame callback.

    The ASTM and HL7 transports differ only in how their per-session
    payload is turned into an :class:`Envelope`. ``to_envelope`` does
    that conversion; the rest (tracked-task scheduling, parse-error
    isolation, pipeline dispatch) is shared.

    :param to_envelope: Callable taking the transport payload (a list
        of ASTM frames or raw HL7 bytes) and returning an
        :class:`Envelope`. May raise — failures are logged and the
        envelope is dropped, but the transport stays up.
    """
    def frame_callback(client, payload):
        task = loop.create_task(
            _run_with_envelope(client, payload, pipeline, to_envelope))
        task_set.add(task)
        task.add_done_callback(task_set.discard)
    return frame_callback


async def _run_with_envelope(client, payload, pipeline, to_envelope):
    try:
        envelope = to_envelope(payload)
    except Exception as exc:
        logger.error(
            "Failed to build envelope from %s: %r", client, exc)
        return
    await pipeline.run(envelope)


def add_lims_arg_group(parser, default_consumer):
    """Append the shared SENAITE LIMS option group to ``parser``.

    All transports take the same connection / auth / retry flags;
    only the default push-consumer name differs (the ASTM and HL7
    transports are wired to different consumers in SENAITE.CORE).
    """
    group = parser.add_argument_group("SENAITE LIMS")
    group.add_argument(
        "-u", "--url", type=str,
        help="SENAITE URL address including username and password "
             "in the format: "
             "http(s)://<user>:<password>@<senaite_url>. Without "
             "--url the server runs in capture-only mode.")
    group.add_argument(
        "-c", "--consumer", type=str, default=default_consumer,
        help="SENAITE push consumer interface")
    group.add_argument(
        "-m", "--message-format", type=str, default="json",
        help="Message format to send to SENAITE.")
    group.add_argument(
        "-r", "--retries", type=int, default=3,
        help="Number of push attempts on transient failures. Only "
             "applies when --url is set.")
    group.add_argument(
        "-d", "--delay", type=int, default=5,
        help="Seconds between push retries. Only applies when "
             "--url is set.")
    return group


def validate_lims(url):
    """Authenticate against SENAITE and return the session, or
    ``None`` when ``url`` is empty.

    Exits the process with status -1 on auth failure so the server
    never starts up half-configured.
    """
    if not url:
        return None
    session = lims.Session(url)
    logger.info("Checking connection to SENAITE ...")
    try:
        session.auth()
    except lims.SenaiteError as exc:
        logger.error("Could not connect to SENAITE: {}".format(exc))
        raise SystemExit(1)
    return session
