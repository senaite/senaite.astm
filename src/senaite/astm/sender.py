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
import os
import sys

from senaite.astm import logger
from senaite.astm.core import lims
from senaite.astm.core.envelope import serialize_envelope
from senaite.astm.core.lims import post_to_senaite
from senaite.astm.utils import parse_capture
from senaite.astm.utils import rebuild_checksums
from senaite.astm.wrapper import Wrapper


def _file_to_message(fh, message_format, rebuild=False):
    """Read a captured ASTM file and produce one message for
    `post_to_senaite`.

    Captures contain raw STX/ETX-framed bytes off the wire (the
    same format `senaite-astm-simulator` writes when it sends a
    fixture to a listener). :func:`senaite.astm.utils.parse_capture`
    extracts the individual frames; `Wrapper` turns them into the
    typed envelope.

    `rebuild=True` runs :func:`rebuild_checksums` over the input
    bytes first so a hand-edited capture (sample-id swap, PHI
    scrub) decodes without the codec asserting on the stale 2-byte
    trailer. Off by default so real wire captures aren't silently
    masked when the bytes were genuinely corrupt.
    """
    raw = fh.read()
    if rebuild:
        raw = rebuild_checksums(raw)
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

    astm_group.add_argument(
        "--rebuild-checksums", action="store_true",
        help="Recompute the 2-byte trailer of every ASTM frame "
             "before parsing. Use this when replaying a capture "
             "that has been hand-edited (sample-id swap, PHI "
             "scrub, etc.) — the edit invalidates the original "
             "checksum and the codec asserts at parse time. Off "
             "by default so genuine wire corruption is not "
             "silently masked.")

    astm_group.add_argument(
        "-o", "--output", type=str, default=None,
        help="Write the converted message(s) instead of pushing "
             "to a LIMS. Use `-` for stdout (single input only); "
             "a directory path to write one file per input "
             "(named <input-stem>.<ext> for the chosen "
             "--message-format); or a regular file path (single "
             "input only). When set, --url is ignored.")

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

    lims_group.add_argument(
        "--dry-run", action="store_true",
        help="Log the URL, consumer, message count and per-message "
             "format + byte size that would be pushed to the LIMS, "
             "then exit without opening a connection. The URL "
             "password is masked. Useful for confirming the right "
             "target and payload before committing.")

    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose logging")

    args = parser.parse_args()

    logger.setLevel(
        logging.DEBUG if args.verbose else logging.INFO)
    logger.addHandler(logging.StreamHandler())

    if not args.infile:
        return
    if not args.output and not args.url:
        logger.error("No --url or --output provided; nothing to do.")
        return

    messages = []
    for fh in args.infile:
        try:
            messages.append((
                getattr(fh, "name", "<stream>"),
                _file_to_message(
                    fh, args.message_format,
                    rebuild=args.rebuild_checksums)))
        except Exception as exc:
            logger.error(
                "Failed to prepare %s as %s: %s",
                getattr(fh, "name", "<stream>"),
                args.message_format, exc)

    if not messages:
        return

    if args.output:
        _write_outputs(messages, args.output, args.message_format)
        return

    if args.dry_run:
        _print_dry_run(
            messages, args.url, args.consumer,
            args.message_format)
        return

    session = lims.Session(args.url)
    post_to_senaite(
        [m for _, m in messages], session,
        retries=args.retries, delay=args.delay,
        consumer=args.consumer)


def _print_dry_run(messages, url, consumer, message_format):
    """Log what would be sent to the LIMS without opening a
    connection. The URL's password component is masked so the
    output is safe to paste into a bug report."""
    logger.info("DRY RUN — no request will be sent")
    logger.info("  url:      %s", _mask_url_password(url))
    logger.info("  consumer: %s", consumer)
    logger.info("  format:   %s", message_format)
    logger.info("  messages: %d", len(messages))
    for path, msg in messages:
        size = len(msg) if msg is not None else 0
        logger.info("    - %s (%d bytes)", path, size)


def _mask_url_password(url):
    """Return `url` with the password component replaced by ***.

    Accepts the project's standard form
    `http(s)://user:password@host[:port]/path`. Returns the URL
    unchanged when no credentials are embedded."""
    if not url or "@" not in url:
        return url or ""
    scheme, _, rest = url.partition("://")
    if "@" not in rest:
        return url
    creds, _, tail = rest.partition("@")
    if ":" not in creds:
        return url
    user, _, _ = creds.partition(":")
    return "{}://{}:***@{}".format(scheme, user, tail)


def _write_outputs(messages, output, message_format):
    """Write converted `messages` to `output` instead of pushing.

    `output` resolves to:

    - `-` — write to stdout. Single input only.
    - existing directory — one file per input named
      `<input-stem>.<ext>` where `<ext>` is derived from the
      message format.
    - any other path — write to that file. Single input only.
    """
    if output == "-":
        if len(messages) > 1:
            logger.error(
                "--output - (stdout) requires a single input; "
                "got %d.", len(messages))
            return
        _write_one(sys.stdout.buffer, messages[0][1])
        return

    if os.path.isdir(output):
        ext = _format_extension(message_format)
        for path, msg in messages:
            stem = os.path.splitext(os.path.basename(path))[0]
            target = os.path.join(output, "{}.{}".format(stem, ext))
            with open(target, "wb") as fh:
                _write_one(fh, msg)
        return

    if len(messages) > 1:
        logger.error(
            "--output %s must be a directory for multi-input "
            "runs; got %d inputs.", output, len(messages))
        return
    with open(output, "wb") as fh:
        _write_one(fh, messages[0][1])


def _write_one(fh, msg):
    if isinstance(msg, str):
        msg = msg.encode("utf-8")
    fh.write(msg)


def _format_extension(message_format):
    return {"json": "json", "astm": "astm", "lis2a": "txt"}.get(
        message_format, "txt")


if __name__ == "__main__":
    main()
