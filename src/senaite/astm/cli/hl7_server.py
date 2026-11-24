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

    _runtime.add_lims_arg_group(
        parser, default_consumer="senaite.core.hl7.import")

    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose logging")
    parser.add_argument(
        "--logfile", default=LOGFILE,
        help="Path to store log files")

    return parser


validate_lims = _runtime.validate_lims


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
    return _runtime.make_frame_callback(
        loop, pipeline, task_set, to_envelope=parse_hl7)


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
    args.session = _runtime.validate_lims(args.url)

    try:
        asyncio.run(amain(args))
    except KeyboardInterrupt:
        logger.info("Interrupted; exiting.")


if __name__ == "__main__":
    main()
