# -*- coding: utf-8 -*-
"""``senaite-hl7-server`` CLI entry point.

Wires the HL7-over-MLLP transport
(:mod:`senaite.astm.transports.hl7.protocol`) to the message
pipeline. The transport hands us raw HL7 bytes per session; this
module parses them into an :class:`Envelope` (same shape the ASTM
transport produces) and runs the pipeline against it.

LIMS push is enabled via ``--url`` the same way as
``senaite-astm-server``. Without ``--url`` the server stays
capture-only (default-off LIMS push per the HemoScreen plan PR-7).
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
from senaite.astm.transports.hl7.parser import parse as parse_hl7
from senaite.astm.transports.hl7.protocol import HL7Protocol

LOGFILE = "senaite-hl7-server.log"
DEFAULT_PORT = "2575"


def _hl7_payload(envelope):
    """DiskCaptureHandler extractor — write the HL7 raw text."""
    return envelope.metadata.hl7 or ""


def build_arg_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    hl7_group = parser.add_argument_group("HL7 SERVER")
    lims_group = parser.add_argument_group("SENAITE LIMS")

    hl7_group.add_argument(
        "-l", "--listen", type=str, default="0.0.0.0",
        help="Listen IP address")
    hl7_group.add_argument(
        "-p", "--port", type=str, default=DEFAULT_PORT,
        help="Port to listen on (default: 2575, IANA-registered "
             "for HL7)")
    hl7_group.add_argument(
        "-o", "--output", type=str,
        help="Output directory to write captured HL7 messages")
    hl7_group.add_argument(
        "--shutdown-grace-seconds", type=int,
        default=_runtime.DEFAULT_SHUTDOWN_GRACE_SECONDS,
        help="Seconds to wait for in-flight handler tasks to "
             "finish before forcefully cancelling them on shutdown.")

    lims_group.add_argument(
        "-u", "--url", type=str,
        help="SENAITE URL address including username and password in "
             "the format: http(s)://<user>:<password>@<senaite_url>. "
             "Without --url the server runs in capture-only mode.")
    lims_group.add_argument(
        "-c", "--consumer", type=str,
        default="senaite.core.hl7.import",
        help="SENAITE push consumer interface")
    lims_group.add_argument(
        "-m", "--message-format", type=str, default="json",
        help="Message format to send to SENAITE. "
             "Allowed formats: 'json', 'hl7'.")
    lims_group.add_argument(
        "-r", "--retries", type=int, default=3,
        help="Number of push attempts on transient failures. Only "
             "applies when --url is set.")
    lims_group.add_argument(
        "-d", "--delay", type=int, default=5,
        help="Seconds between push retries. Only applies when "
             "--url is set.")

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
        handlers.append(DiskCaptureHandler(
            os.path.abspath(args.output),
            payload=_hl7_payload,
            ext=".hl7"))
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
    """Build the protocol callback that turns raw HL7 bytes into a
    pipeline run.

    The transport hands us bytes already stripped of MLLP framing.
    We parse them into an envelope and schedule a tracked task so
    shutdown can wait for in-flight handlers.
    """
    def frame_callback(client, hl7_bytes):
        task = loop.create_task(
            _process(client, hl7_bytes, pipeline))
        task_set.add(task)
        task.add_done_callback(task_set.discard)
    return frame_callback


async def _process(client, hl7_bytes, pipeline):
    try:
        envelope = parse_hl7(hl7_bytes)
    except Exception as exc:
        logger.error(
            "Failed to parse HL7 message from %s: %r", client, exc)
        return
    await pipeline.run(envelope)


async def amain(args, stop_event=None):
    loop = asyncio.get_running_loop()
    task_set = set()
    pipeline = build_pipeline(args, args.session)
    frame_callback = make_frame_callback(loop, pipeline, task_set)

    server = await loop.create_server(
        lambda: HL7Protocol(frame_callback=frame_callback),
        host=args.listen, port=args.port)

    for socket in server.sockets:
        ip, port = socket.getsockname()
        logger.info("Starting HL7 server on {}:{}".format(ip, port))
    if args.session is None:
        logger.info(
            "HL7 server ready (capture-only; no --url configured)")
    else:
        logger.info("HL7 server ready to handle connections ...")

    if stop_event is None:
        stop_event = asyncio.Event()
    _runtime.install_shutdown_handlers(loop, stop_event)

    try:
        await stop_event.wait()
    finally:
        logger.info("Shutting down HL7 server...")
        server.close()
        await server.wait_closed()
        await _runtime.drain_tasks(task_set, args.shutdown_grace_seconds)
        logger.info("HL7 server is now down...")


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
