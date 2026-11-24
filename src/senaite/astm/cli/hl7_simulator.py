# -*- coding: utf-8 -*-
"""``senaite-hl7-simulator``: replay HL7 fixtures against a server.

Reads one or more HL7 v2 fixtures from disk, wraps each in MLLP
framing, sends them sequentially over a single TCP connection to a
``senaite-hl7-server`` instance, and waits for the matching ACK
before sending the next.

The fixture file may contain segments separated by ``\\n`` (typical
for human-edited captures) or ``\\r`` (HL7 on the wire); the
simulator normalises to ``\\r`` before sending.
"""

import argparse
import asyncio
import logging
import os
import sys

from senaite.astm import logger
from senaite.astm.transports.hl7.framing import MLLP_END
from senaite.astm.transports.hl7.framing import SB
from senaite.astm.transports.hl7.framing import extract_messages
from senaite.astm.transports.hl7.framing import wrap


def normalise(payload):
    """Normalise newlines to HL7 segment terminators (``\\r``).

    Stripping any trailing terminator keeps the wrapped payload from
    ending in a stray empty segment.
    """
    payload = payload.replace(b"\r\n", b"\r").replace(b"\n", b"\r")
    return payload.rstrip(b"\r")


async def send_fixture(host, port, path, delay):
    with open(path, "rb") as fh:
        payload = normalise(fh.read())

    framed = wrap(payload)
    logger.info("Sending %s (%d bytes payload)", path, len(payload))

    reader, writer = await asyncio.open_connection(host, port)
    try:
        writer.write(framed)
        await writer.drain()

        ack = await read_one_message(reader)
        if ack is None:
            logger.error("No ACK received for %s", path)
        else:
            logger.info("ACK received: %r", ack[:120])

        if delay:
            await asyncio.sleep(delay)
    finally:
        writer.close()
        await writer.wait_closed()


async def read_one_message(reader, deadline=5.0):
    """Read until exactly one MLLP-framed HL7 message has arrived."""
    buffer = b""
    while True:
        try:
            chunk = await asyncio.wait_for(reader.read(1024),
                                           timeout=deadline)
        except asyncio.TimeoutError:
            return None
        if not chunk:
            return None
        buffer += chunk
        messages, buffer = extract_messages(buffer)
        if messages:
            return messages[0]


def build_arg_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "-a", "--address", type=str, default="127.0.0.1",
        help="Server address")
    parser.add_argument(
        "-p", "--port", type=int, default=2575,
        help="Server port")
    parser.add_argument(
        "-i", "--infile", type=str, nargs="+", required=True,
        help="One or more HL7 fixture files to replay")
    parser.add_argument(
        "-d", "--delay", type=float, default=0.0,
        help="Seconds to wait between fixtures")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose logging")
    return parser


async def amain(args):
    for path in args.infile:
        if not os.path.isfile(path):
            logger.error("Fixture not found: %s", path)
            return 1
        await send_fixture(args.address, args.port, path, args.delay)
    return 0


def main():
    args = build_arg_parser().parse_args()
    logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    logger.addHandler(logging.StreamHandler())
    sys.exit(asyncio.run(amain(args)) or 0)


# Re-exports for tests that prefer to import the framing names from
# the simulator namespace.
__all__ = ["main", "send_fixture", "normalise", "SB", "MLLP_END"]


if __name__ == "__main__":
    main()
