# -*- coding: utf-8 -*-
"""HL7 v2 → :class:`Envelope` parser.

Turns a raw HL7 message (bytes, as captured by
:mod:`senaite.astm.transports.hl7.protocol`) into the same
:class:`Envelope` shape the ASTM transport produces, so downstream
consumers depend on one schema regardless of which transport the
device speaks.

Segment-to-bucket mapping:

================== ==============================
HL7 segment         Envelope bucket
================== ==============================
``MSH``             :attr:`Envelope.H`
``PID``             :attr:`Envelope.P`
``OBR``             :attr:`Envelope.O`
``OBX``             :attr:`Envelope.R`
``NTE``             :attr:`Envelope.C`
================== ==============================

The raw HL7 text lands in :attr:`Metadata.hl7` so disk capture and
"send the original bytes" flows still work without re-encoding.

This module is intentionally lean: it does not interpret OBX values,
units, or flags. The HemoScreen-specific keyword mapping and
``OBR-4`` routing live in the instrument adapter (PR-8).
"""

import hl7

from senaite.astm.core.envelope import Envelope, Metadata

DEFAULT_ENCODING = "utf-8"

# Bucket names mirror the ASTM record types the Envelope already
# carries. Mapping HL7 segments onto them keeps the public envelope
# schema transport-agnostic.
SEGMENT_BUCKETS = {
    "MSH": "H",
    "PID": "P",
    "OBR": "O",
    "OBX": "R",
    "NTE": "C",
}


def _decode(raw):
    """Return ``raw`` as a string regardless of input type."""
    if isinstance(raw, bytes):
        return raw.decode(DEFAULT_ENCODING, errors="replace")
    return raw


def _normalise_segments(text):
    """Ensure inter-segment terminators are ``\\r``.

    Captured files may end up with mixed line endings depending on
    how they were stored on disk. HL7 itself uses ``\\r``.
    """
    return text.replace("\r\n", "\r").replace("\n", "\r")


def _segment_to_dict(segment):
    """Convert one :class:`hl7.Segment` into ``{ "1": ..., "2": ... }``.

    Keys are stringified sequence numbers; fields with subcomponents
    are rendered as plain strings (joined by the original delimiter
    characters preserved by the ``hl7`` package).

    HL7's MSH numbering is irregular (MSH-1 is the field separator,
    MSH-2 is the encoding characters), but the ``hl7`` package
    transparently aligns indices so segment[3] is MSH-3, segment[1]
    is PID-1 etc. We mirror those indices.
    """
    out = {}
    # Skip index 0 — that's the segment name itself.
    for idx in range(1, len(segment)):
        out[str(idx)] = str(segment[idx])
    return out


def parse(raw):
    """Parse a raw HL7 v2 message into an :class:`Envelope`.

    :param raw: HL7 bytes (or string). MLLP framing must already be
        stripped by the transport layer — this function expects only
        the inner payload (segments separated by ``\\r`` or ``\\n``).
    :returns: A fully-populated :class:`Envelope`. The raw payload
        is stored verbatim in :attr:`Metadata.hl7`.
    :raises ValueError: when the input cannot be parsed as HL7 at
        all (no MSH segment, etc.).
    """
    text = _normalise_segments(_decode(raw))
    if not text.endswith("\r"):
        text = text + "\r"

    try:
        message = hl7.parse(text)
    except Exception as exc:
        raise ValueError(
            "Failed to parse HL7 message: {}".format(exc)) from exc

    buckets = {bucket: [] for bucket in SEGMENT_BUCKETS.values()}
    for segment in message:
        name = str(segment[0])
        bucket = SEGMENT_BUCKETS.get(name)
        if bucket is None:
            # Unknown segment — preserve as a generic dict under its
            # own key so consumers can still see it without us
            # silently dropping data.
            continue
        buckets[bucket].append(_segment_to_dict(segment))

    metadata = Metadata(hl7=text.rstrip("\r"))
    return Envelope(metadata=metadata, **buckets)
