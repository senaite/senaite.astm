# -*- coding: utf-8 -*-
"""``senaite-hl7-server`` CLI entry point.

Passthrough HL7-over-MLLP listener. Captures each received HL7 v2
message verbatim to ``--output`` and responds with a comm-level
ACK^R01. **No** parsing-to-envelope, **no** LIMS push — that arrives
in PR-7 (parser) and PR-8 (HemoScreen adapter) once we have real
device captures to validate against.

The lifecycle scaffolding (logging, signal handlers, task draining)
is reused from :mod:`senaite.astm.cli._runtime`.
"""

import argparse
import asyncio
import os

from senaite.astm import logger
from senaite.astm.cli import _runtime
from senaite.astm.core.pipeline import Pipeline
from senaite.astm.transports.hl7.protocol import HL7Protocol
from senaite.astm.utils import write_message

LOGFILE = "senaite-hl7-server.log"
DEFAULT_PORT = "2575"


class RawCaptureHandler(object):
    """Persist a raw HL7 payload to disk, one file per message.

    Mirrors :class:`senaite.astm.core.output.DiskCaptureHandler` but
    operates on raw bytes rather than an :class:`Envelope`. Lives in
    this module for now because PR-6 is HL7-passthrough-only; if a
    second transport needs the same primitive it can promote to
    :mod:`senaite.astm.core.output`.
    """

    name = "raw_capture"

    def __init__(self, path, ext=".hl7"):
        self.path = path
        self.ext = ext

    async def __call__(self, payload):
        if not self.path:
            return
        await asyncio.to_thread(write_message, payload, self.path,
                                ext=self.ext)


def build_arg_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        "-l", "--listen", type=str, default="0.0.0.0",
        help="Listen IP address")
    parser.add_argument(
        "-p", "--port", type=str, default=DEFAULT_PORT,
        help="Port to listen on (default: 2575, IANA-registered "
             "for HL7)")
    parser.add_argument(
        "-o", "--output", type=str,
        help="Output directory to write captured HL7 messages")
    parser.add_argument(
        "--shutdown-grace-seconds", type=int,
        default=_runtime.DEFAULT_SHUTDOWN_GRACE_SECONDS,
        help="Seconds to wait for in-flight handler tasks to "
             "finish before forcefully cancelling them on shutdown.")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose logging")
    parser.add_argument(
        "--logfile", default=LOGFILE,
        help="Path to store log files")

    return parser


def build_pipeline(args):
    handlers = []
    if args.output:
        handlers.append(RawCaptureHandler(os.path.abspath(args.output)))
    return Pipeline(handlers)


async def amain(args, stop_event=None):
    loop = asyncio.get_running_loop()
    task_set = set()
    pipeline = build_pipeline(args)
    dispatch = _runtime.make_tracked_dispatcher(loop, pipeline, task_set)

    server = await loop.create_server(
        lambda: HL7Protocol(frame_callback=dispatch),
        host=args.listen, port=args.port)

    for socket in server.sockets:
        ip, port = socket.getsockname()
        logger.info("Starting HL7 server on {}:{}".format(ip, port))
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

    try:
        asyncio.run(amain(args))
    except KeyboardInterrupt:
        logger.info("Interrupted; exiting.")


if __name__ == "__main__":
    main()
