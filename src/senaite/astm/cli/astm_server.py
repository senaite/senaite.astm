# -*- coding: utf-8 -*-
"""``senaite-astm-server`` CLI entry point.

Wires the slim ASTM transport (``transports/astm/protocol.py``) to
the message :class:`Pipeline`. The transport emits complete frame
batches; this module wraps them into an :class:`Envelope` and runs
the pipeline against it.

The CLI surface (arguments, default ports, logfile name) is
preserved from the previous ``senaite.astm.server`` module.
"""

import argparse
import asyncio
import contextlib
import logging
import logging.handlers
import os
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
        # NOTE: maxBytes=5 is preserved from the legacy server for
        # behavioural parity. PR-G fixes this to a sane value.
        handler = logging.handlers.RotatingFileHandler(
            args.logfile, maxBytes=5, backupCount=0)
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


def make_frame_callback(loop, queue):
    """Return a frame callback that pushes ``(client, frames)`` onto
    the asyncio queue from the protocol's sync context.
    """
    def frame_callback(client, frames):
        loop.call_soon_threadsafe(queue.put_nowait, (client, frames))
    return frame_callback


async def consume(queue, pipeline):
    """Consume frame batches off the queue and run the pipeline."""
    while True:
        client, frames = await queue.get()
        try:
            envelope = Wrapper(frames).to_envelope()
        except Exception as exc:
            logger.error(
                "Failed to wrap %d frames from %s: %r",
                len(frames), client, exc)
            continue
        await pipeline.run(envelope)


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    configure_logging(args)
    validate_output(args.output)
    session = validate_lims(args.url)

    loop = asyncio.get_event_loop()
    queue = asyncio.Queue()
    pipeline = build_pipeline(args, session)
    frame_callback = make_frame_callback(loop, queue)

    loop.create_task(consume(queue, pipeline))

    server_coro = loop.create_server(
        lambda: ASTMProtocol(frame_callback=frame_callback),
        host=args.listen, port=args.port)
    server = loop.run_until_complete(server_coro)

    for socket in server.sockets:
        ip, port = socket.getsockname()
        logger.info("Starting server on {}:{}".format(ip, port))
        logger.info("ASTM server ready to handle connections ...")

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        all_tasks = asyncio.gather(
            *asyncio.all_tasks(loop), return_exceptions=True)
        all_tasks.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            loop.run_until_complete(all_tasks)
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        loop.close()
        logger.info("Server is now down...")


if __name__ == "__main__":
    main()
