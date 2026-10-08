# -*- coding: utf-8 -*-
"""``senaite-emerald-server`` CLI entry point.

Wires the CELL-DYN Emerald transport
(:mod:`senaite.astm.transports.emerald.protocol`) to the message
pipeline. The transport hands us the raw bytes of each complete frame;
this module persists them, parses them into an :class:`Envelope` (same
shape the ASTM transport produces) and pushes the results of samples to
the LIMS.

The frame is only acknowledged to the instrument once it has been
written to ``--output``: in handshake mode, the instrument does not tag as
sent the results that were not acknowledged, and proposes to send them
again at next login. The push to the LIMS runs afterwards, in the
background, so a slow or unreachable LIMS does not delay the acknowledge.

Frames that are not about a sample (QC, calibration, repeatability,
start-up) are captured, but not pushed to the LIMS.

LIMS push is enabled via ``--url`` the same way as
``senaite-astm-server``. Without ``--url`` the server stays capture-only.
The default consumer is the one of the ASTM transport, so the LIMS
resolves the importer by the sender name of the frame header (e.g.
``EMD22AL``).
"""

import argparse
import asyncio
import os

from senaite.astm import logger
from senaite.astm.cli import _runtime
from senaite.astm.core.lims import LimsPushHandler
from senaite.astm.core.pipeline import Pipeline
from senaite.astm.transports.emerald.parser import parse as parse_emerald
from senaite.astm.transports.emerald.protocol import EmeraldProtocol
from senaite.astm.utils import write_message

LOGFILE = "senaite-emerald-server.log"

# Default host port of the instrument (COMMUNICATION / NET. PARAM.)
DEFAULT_PORT = "1200"


def build_arg_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    group = parser.add_argument_group("CELL-DYN EMERALD SERVER")
    group.add_argument(
        "-l", "--listen", type=str, default="0.0.0.0",
        help="Listen IP address")
    group.add_argument(
        "-p", "--port", type=str, default=DEFAULT_PORT,
        help="Port to listen on. The default is the default host port "
             "of the instrument")
    group.add_argument(
        "-o", "--output", type=str,
        help="Output directory to write captured frames")
    group.add_argument(
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


validate_lims = _runtime.validate_lims


def is_sample_result(envelope):
    """Returns whether the envelope holds the results of a sample
    """
    return bool(envelope.O and envelope.R)


def build_pipeline(args, session):
    """Returns the pipeline that runs once the frame is captured. Only the
    results of samples are pushed to the LIMS
    """
    handlers = []
    if session is not None:
        push = LimsPushHandler(
            session,
            retries=args.retries,
            delay=args.delay,
            consumer=args.consumer,
            message_format=args.message_format,
        )

        async def push_sample_results(envelope):
            if is_sample_result(envelope):
                await push(envelope)

        handlers.append(push_sample_results)
    return Pipeline(handlers)


def make_frame_callback(loop, pipeline, task_set, output=None):
    """Build the protocol callback for complete frames

    The callback returns an awaitable that is done once the frame is
    written to ``output`` (if set), so the protocol acknowledges the frame
    afterwards. The frame is then parsed into an envelope and the pipeline
    runs as a tracked task, so shutdown can wait for in-flight handlers.
    """
    async def capture(frame):
        if output:
            await asyncio.to_thread(write_message, frame, output, ext=".txt")
        return True

    async def process(client, frame):
        try:
            envelope = parse_emerald(frame)
        except Exception as exc:
            logger.error(
                "Failed to build envelope from %s: %r", client, exc)
            return
        await pipeline.run(envelope)

    def frame_callback(client, frame):
        captured = loop.create_task(capture(frame))

        def on_captured(task):
            if task.cancelled() or task.exception():
                return
            processing = loop.create_task(process(client, frame))
            task_set.add(processing)
            processing.add_done_callback(task_set.discard)

        captured.add_done_callback(on_captured)
        task_set.add(captured)
        captured.add_done_callback(task_set.discard)
        return captured

    return frame_callback


async def amain(args, stop_event=None):
    loop = asyncio.get_running_loop()
    task_set = set()
    pipeline = build_pipeline(args, args.session)
    output = os.path.abspath(args.output) if args.output else None
    frame_callback = make_frame_callback(
        loop, pipeline, task_set, output=output)

    server = await loop.create_server(
        lambda: EmeraldProtocol(frame_callback=frame_callback),
        host=args.listen, port=args.port)

    for socket in server.sockets:
        ip, port = socket.getsockname()
        logger.info("Starting CELL-DYN Emerald server on {}:{}".format(
            ip, port))
    if args.session is None:
        logger.info("CELL-DYN Emerald server ready (capture-only; no "
                    "--url configured)")
    else:
        logger.info("CELL-DYN Emerald server ready to handle "
                    "connections ...")

    if stop_event is None:
        stop_event = asyncio.Event()
    _runtime.install_shutdown_handlers(loop, stop_event)

    try:
        await stop_event.wait()
    finally:
        logger.info("Shutting down CELL-DYN Emerald server...")
        server.close()
        await server.wait_closed()
        await _runtime.drain_tasks(task_set, args.shutdown_grace_seconds)
        logger.info("CELL-DYN Emerald server is now down...")


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
