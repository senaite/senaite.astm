# -*- coding: utf-8 -*-
"""`senaite-astm-send` CLI — push captured ASTM files to a SENAITE
LIMS push endpoint without running a TCP listener.

Useful for replaying messages from `astm_messages/` directly into a
dev / staging SENAITE instance so the consumer-side adapter (e.g.
`cermel.lims.adapters.astm_importer.ASTMImporter`) can be
exercised end-to-end without the device on the wire.

The `-m / --message-format` option mirrors `senaite-astm-server`'s
flag: choose what the LIMS receives.

- `json`  (default): parse each input file into an :class:`Envelope`
  and POST the typed JSON. This is what the
  `senaite.core.lis2a.import` consumer expects today.
- `astm`  : POST the original framed ASTM bytes verbatim (legacy
  consumers that re-parse raw payloads).
- `lis2a` : POST the framed-free LIS2-A flat string from
  `metadata.lis2a` (other legacy paths).
"""

import argparse
import logging

from senaite.astm import logger
from senaite.astm.core import lims
from senaite.astm.core.envelope import serialize_envelope
from senaite.astm.core.lims import post_to_senaite
from senaite.astm.utils import parse_capture
from senaite.astm.wrapper import Wrapper


def _file_to_message(fh, message_format):
    """Read a captured ASTM file and produce one message for
    `post_to_senaite`.

    Captures contain raw STX/ETX-framed bytes off the wire (the
    same format `senaite-astm-simulator` writes when it sends a
    fixture to a listener). :func:`senaite.astm.utils.parse_capture`
    extracts the individual frames; `Wrapper` turns them into the
    typed envelope.
    """
    raw = fh.read()
    if message_format == "astm":
        return raw

    frames = parse_capture(raw)
    envelope = Wrapper(frames).to_envelope()
    return serialize_envelope(envelope, message_format)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=__doc__.splitlines()[0])

    astm_group = parser.add_argument_group("ASTM")
    lims_group = parser.add_argument_group("SENAITE LIMS")

    astm_group.add_argument(
        "-i", "--infile",
        type=argparse.FileType("rb"), nargs="+",
        help="ASTM file(s) to send to SENAITE")

    lims_group.add_argument(
        "-u", "--url", type=str,
        help="SENAITE URL with credentials in the format "
             "http(s)://<user>:<password>@<senaite_url>")

    lims_group.add_argument(
        "-c", "--consumer", type=str,
        default="senaite.core.lis2a.import",
        help="SENAITE push consumer interface")

    lims_group.add_argument(
        "-m", "--message-format", type=str, default="json",
        choices=("json", "astm", "lis2a"),
        help="Format of the messages sent to SENAITE. `json` parses "
             "each input file into a typed envelope and POSTs it as "
             "JSON (matches the default of `senaite-astm-server`); "
             "`astm` and `lis2a` send the raw payload variants.")

    lims_group.add_argument(
        "-r", "--retries", type=int, default=3,
        help="Number of push attempts on transient failures")

    lims_group.add_argument(
        "-d", "--delay", type=int, default=5,
        help="Seconds between push retries")

    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose logging")

    args = parser.parse_args()

    logger.setLevel(
        logging.DEBUG if args.verbose else logging.INFO)
    logger.addHandler(logging.StreamHandler())

    if not args.infile:
        return
    if not args.url:
        logger.error("No --url provided; nothing to do.")
        return

    messages = []
    for fh in args.infile:
        try:
            messages.append(_file_to_message(fh, args.message_format))
        except Exception as exc:
            logger.error(
                "Failed to prepare %s as %s: %s",
                getattr(fh, "name", "<stream>"),
                args.message_format, exc)

    if not messages:
        return

    session = lims.Session(args.url)
    post_to_senaite(
        messages, session,
        retries=args.retries, delay=args.delay,
        consumer=args.consumer)


if __name__ == "__main__":
    main()
