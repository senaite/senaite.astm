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

LOGFILE_MAX_BYTES = 10 * 1024 * 1024
LOGFILE_BACKUP_COUNT = 5
DEFAULT_SHUTDOWN_GRACE_SECONDS = 30


def configure_logging(args):
    """Attach the rotating logfile + stream handlers to the package
    logger and set the verbosity from ``args.verbose``."""
    if getattr(args, "logfile", None):
        handler = logging.handlers.RotatingFileHandler(
            args.logfile,
            maxBytes=LOGFILE_MAX_BYTES,
            backupCount=LOGFILE_BACKUP_COUNT)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-8s %(message)s"))
        logger.addHandler(handler)

    logger.setLevel(
        logging.DEBUG if getattr(args, "verbose", False) else logging.INFO)
    logger.addHandler(logging.StreamHandler())


def validate_output(output):
    """Exit with an error if ``output`` is set but not a directory."""
    if output and not os.path.isdir(output):
        logger.error("Output path must be an existing directory")
        sys.exit(-1)


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
