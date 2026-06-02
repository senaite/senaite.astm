# -*- coding: utf-8 -*-
"""`senaite-astm-inspect` CLI — read-only introspection of captured
ASTM files.

Three subcommands, picked at parse time, so a UI on top of
senaite.astm has a single command surface to scrape:

- ``instrument FILE [FILE ...]`` — print the canonical instrument
  name resolved from each file's header.
- ``summary FILE [FILE ...]`` — one line per file with instrument,
  sample id, and per-bucket record counts.
- ``diff FILE_A FILE_B`` — structural diff of the two parsed
  envelopes (per-bucket counts and the JSON-encoded buckets).

All three modes parse the capture into the typed envelope and
work from there. No LIMS push, no writes — safe to run against
production captures.
"""

import argparse
import difflib
import json
import sys

import senaite.astm.instruments  # noqa: F401  side-effect: register
from senaite.astm.core.instrument import find_instrument
from senaite.astm.core.envelope import serialize_envelope
from senaite.astm.utils import parse_capture
from senaite.astm.wrapper import Wrapper


RECORD_TYPES = ("H", "P", "O", "R", "C", "M", "L", "Q")


def _read_envelope(path):
    """Parse one capture file into the typed envelope."""
    with open(path, "rb") as fh:
        raw = fh.read()
    frames = parse_capture(raw)
    return Wrapper(frames).to_envelope(), frames


def _resolve_instrument(frames):
    """Return the canonical instrument name resolved from the
    capture's first frame, or `"unknown"`."""
    if not frames:
        return "unknown"
    instrument = find_instrument(frames[0])
    return instrument.name if instrument else "unknown"


def _sample_id(envelope):
    """Best-effort sample id extraction from the first Order
    record. Returns an empty string when no Order is present or
    the field is missing — vendor-specific shapes are surfaced
    by the consumer adapter, not this introspection tool."""
    if not envelope.O:
        return ""
    order = envelope.O[0]
    return str(order.get("sample_id") or "")


def _bucket_counts(envelope):
    return {rt: len(getattr(envelope, rt)) for rt in RECORD_TYPES}


def cmd_instrument(args, stream):
    for path in args.files:
        try:
            _env, frames = _read_envelope(path)
        except Exception as exc:
            stream.write("%s: ERROR %s\n" % (path, exc))
            continue
        stream.write("%s: %s\n" % (path, _resolve_instrument(frames)))
    return 0


def cmd_summary(args, stream):
    for path in args.files:
        try:
            env, frames = _read_envelope(path)
        except Exception as exc:
            stream.write("%s: ERROR %s\n" % (path, exc))
            continue
        counts = _bucket_counts(env)
        parts = ["%s=%d" % (rt, counts[rt]) for rt in RECORD_TYPES]
        stream.write(
            "%s: instrument=%s sample_id=%s %s\n" % (
                path,
                _resolve_instrument(frames),
                _sample_id(env) or "-",
                " ".join(parts)))
    return 0


def cmd_diff(args, stream):
    env_a, _ = _read_envelope(args.file_a)
    env_b, _ = _read_envelope(args.file_b)
    a = json.loads(serialize_envelope(env_a, "json"))
    b = json.loads(serialize_envelope(env_b, "json"))
    text_a = json.dumps(a, indent=2, sort_keys=True).splitlines()
    text_b = json.dumps(b, indent=2, sort_keys=True).splitlines()
    diff = difflib.unified_diff(
        text_a, text_b,
        fromfile=args.file_a, tofile=args.file_b, lineterm="")
    wrote_any = False
    for line in diff:
        stream.write(line + "\n")
        wrote_any = True
    return 1 if wrote_any else 0


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="senaite-astm-inspect",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    sp_inst = sub.add_parser(
        "instrument",
        help="Print the resolved instrument name for each file")
    sp_inst.add_argument("files", nargs="+", metavar="FILE")
    sp_inst.set_defaults(func=cmd_instrument)

    sp_sum = sub.add_parser(
        "summary",
        help="One-line summary (instrument + counts) per file")
    sp_sum.add_argument("files", nargs="+", metavar="FILE")
    sp_sum.set_defaults(func=cmd_summary)

    sp_diff = sub.add_parser(
        "diff",
        help="Structural diff of two parsed envelopes")
    sp_diff.add_argument("file_a", metavar="FILE_A")
    sp_diff.add_argument("file_b", metavar="FILE_B")
    sp_diff.set_defaults(func=cmd_diff)

    return parser


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args, sys.stdout)


if __name__ == "__main__":
    sys.exit(main())
