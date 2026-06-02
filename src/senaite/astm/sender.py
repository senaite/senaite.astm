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

# Conservative default set of P-record keys that almost always
# carry identifying / medical information. The full P record has
# 30+ fields (see senaite.astm.records.PatientRecord); this set
# targets the obvious ones. Use --scrub-phi-extra-fields to add
# vendor-specific keys not covered here.
PHI_KEYS = (
    "name",
    "maiden_name",
    "birthdate",
    "address",
    "phone",
    "id",
    "physician_id",
    "diagnosis",
    "medication",
)
PHI_REDACTION = "<REDACTED>"


def _file_to_message(fh, message_format, rebuild=False,
                     substitutions=None,
                     scrub_phi=False, phi_extra=()):
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

    `substitutions` is an optional list of `(old, new)` byte pairs
    applied to the raw bytes before any other processing. Used
    primarily to retarget the sample id of a captured message
    (`CLVB262200 -> CLVB262205`) so the same fixture can be
    replayed against successive registrations. Any substitution
    that changes a frame body invalidates the trailing checksum,
    so the typical companion flag is `--rebuild-checksums`.

    `scrub_phi=True` replaces the values of well-known
    patient-identifying keys in every P record with `<REDACTED>`
    before the envelope is serialised. Only the parsed-JSON path
    can be scrubbed safely; raw ASTM bytes and the flat LIS2-A
    text in `metadata.*` are not rewritten, so the caller should
    use `-m json`. `phi_extra` adds vendor-specific keys to the
    default set (see :data:`PHI_KEYS`).
    """
    raw = fh.read()
    if substitutions:
        raw = _apply_substitutions(raw, substitutions)
    if rebuild:
        raw = rebuild_checksums(raw)
    if message_format == "astm":
        return raw

    frames = parse_capture(raw)
    envelope = Wrapper(frames).to_envelope()
    if scrub_phi:
        _scrub_envelope_phi(envelope, phi_extra)
    return serialize_envelope(envelope, message_format)


def _apply_substitutions(raw, substitutions):
    """Apply each `(old, new)` byte pair to `raw` in order.

    Plain `bytes.replace` — global, literal, no regex. Order
    matters only when the user supplies pairs that overlap each
    other, in which case the explicit ordering is the only sane
    contract.
    """
    for old, new in substitutions:
        raw = raw.replace(old, new)
    return raw


def _parse_substitution(value):
    """Argparse type converter for `--substitute-sample-id`.

    Accepts `OLD=NEW`; rejects forms with no `=` or an empty side.
    Returns the pair as bytes (latin-1; ASTM payloads are 8-bit
    clean), so the substitution can be applied directly to the
    raw capture stream without an intermediate decode.
    """
    if "=" not in value:
        raise argparse.ArgumentTypeError(
            "expected OLD=NEW, got %r" % value)
    old, new = value.split("=", 1)
    if not old:
        raise argparse.ArgumentTypeError(
            "OLD side of substitution is empty: %r" % value)
    return (old.encode("latin-1"), new.encode("latin-1"))


def _scrub_envelope_phi(envelope, extra_keys=()):
    """Replace the values of PHI keys in every P record of
    `envelope` with :data:`PHI_REDACTION`, in place.

    Also drops the verbatim flat-text payloads in `metadata.astm`
    and `metadata.lis2a` so a JSON-scrubbed message can't be
    pulled back to its un-scrubbed raw form by a downstream
    consumer that only looks at metadata.
    """
    keys = set(PHI_KEYS) | set(extra_keys)
    for patient in envelope.P:
        for key in list(patient.keys()):
            if key in keys and patient[key]:
                patient[key] = PHI_REDACTION
    if envelope.metadata.astm:
        envelope.metadata.astm = ""
    if envelope.metadata.lis2a:
        envelope.metadata.lis2a = ""


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
        "--substitute-sample-id", dest="substitutions",
        action="append", default=[], metavar="OLD=NEW",
        type=_parse_substitution,
        help="Replace every occurrence of OLD with NEW in the raw "
             "capture before parsing. Repeatable. Primary use: "
             "retarget a captured ASTM file to a different sample "
             "id so the same fixture can be replayed against a "
             "fresh registration without editing the file. The "
             "substitution invalidates the affected frame's "
             "checksum, so combine with --rebuild-checksums.")

    astm_group.add_argument(
        "--validate-only", action="store_true",
        help="Parse each input file into the typed envelope and "
             "report success or failure per file. Does not push to "
             "a LIMS and does not write any output. Exits with a "
             "non-zero status equal to the number of files that "
             "failed to parse. Useful as a CI check that a captured "
             "fixture still rounds through the codec + envelope "
             "schema after changes to either.")

    astm_group.add_argument(
        "--scrub-phi", action="store_true",
        help="Redact patient-identifying fields in every P record "
             "(name, birthdate, address, phone, IDs, diagnosis, "
             "medication) with '<REDACTED>' before serialising. "
             "Also clears the verbatim metadata.astm / "
             "metadata.lis2a payloads so the un-scrubbed bytes "
             "do not leak through. Requires --message-format json; "
             "the raw / flat formats cannot be rewritten safely.")

    astm_group.add_argument(
        "--scrub-phi-extra-field", dest="phi_extra",
        action="append", default=[], metavar="KEY",
        help="Additional P-record key to redact under --scrub-phi. "
             "Repeatable; vendor-specific keys not covered by the "
             "default set go here.")

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

    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose logging")

    args = parser.parse_args()

    logger.setLevel(
        logging.DEBUG if args.verbose else logging.INFO)
    logger.addHandler(logging.StreamHandler())

    if not args.infile:
        return

    if args.validate_only:
        sys.exit(_validate_only(args.infile, args.rebuild_checksums))

    if args.scrub_phi and args.message_format != "json":
        logger.error(
            "--scrub-phi requires --message-format json; "
            "raw ASTM bytes and the flat LIS2-A text cannot be "
            "rewritten safely.")
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
                    rebuild=args.rebuild_checksums,
                    substitutions=args.substitutions,
                    scrub_phi=args.scrub_phi,
                    phi_extra=args.phi_extra)))
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

    session = lims.Session(args.url)
    post_to_senaite(
        [m for _, m in messages], session,
        retries=args.retries, delay=args.delay,
        consumer=args.consumer)


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


def _validate_only(infiles, rebuild):
    """Parse each capture into the typed envelope and report
    success or failure per file. Returns the number of failures
    (so the CLI exit code is `failure-count`)."""
    failures = 0
    for fh in infiles:
        name = getattr(fh, "name", "<stream>")
        try:
            _file_to_message(fh, "json", rebuild=rebuild)
        except Exception as exc:
            failures += 1
            logger.error("INVALID %s: %s", name, exc)
            continue
        logger.info("OK      %s", name)
    return failures


def _write_one(fh, msg):
    if isinstance(msg, str):
        msg = msg.encode("utf-8")
    fh.write(msg)


def _format_extension(message_format):
    return {"json": "json", "astm": "astm", "lis2a": "txt"}.get(
        message_format, "txt")


if __name__ == "__main__":
    main()
