# -*- coding: utf-8 -*-
"""Decoder for `<DTYPE>-stream/<COMPRESSION>:<ENCODING>^<payload>`.

Some instruments (e.g. the Horiba Yumizen H500/H550 hematology
analyzers) embed binary numeric arrays in ASTM `M` records using a
small self-describing convention:

    FLOATLE-stream/deflate:base64^Y2AAg...

reads as: a little-endian 32-bit float stream, deflate-compressed,
base64-encoded. The payload after `^` is the encoded bytes.

The convention is generic: any dtype/compression/encoding triple
the device names can be supported by this decoder. Today only the
combinations Yumizen actually emits are implemented; new triples
are easy to add.

This module is vendor-neutral on purpose. Individual instrument
modules (e.g. `senaite.astm.instruments.horiba_yumizen_h5xx`)
declare which of their fields carry encoded streams and call
:func:`decode_stream` to surface the numeric arrays in the
envelope.
"""

import base64
import struct
import zlib

# Map a `<DTYPE>` token to its `struct` format character and item
# byte size. Add a row to support a new dtype.
_DTYPES = {
    "FLOATLE":  ("<f", 4),
    "FLOATBE":  (">f", 4),
    "INT32LE":  ("<i", 4),
    "INT32BE":  (">i", 4),
    "INT16LE":  ("<h", 2),
    "INT16BE":  (">h", 2),
}


def is_encoded_stream(value):
    """Return True when `value` looks like an encoded stream.

    Cheap shape check used by :class:`EncodedStreamField` to decide
    whether to attempt the decode pipeline or pass the value
    through unchanged.
    """
    if not isinstance(value, str):
        return False
    if "-stream/" not in value:
        return False
    if "^" not in value:
        return False
    return True


def decode_stream(value):
    """Decode an encoded stream into a list of numeric values.

    :param value: A string of shape
        `<DTYPE>-stream/<COMPRESSION>:<ENCODING>^<payload>`,
        e.g. `FLOATLE-stream/deflate:base64^Y2AAg...`.
    :returns: Plain Python list of decoded numeric values (the
        item type depends on the dtype token).
    :raises ValueError: when the prefix is missing, references an
        unsupported dtype/compression/encoding, or the payload
        cannot be decoded.
    """
    if not is_encoded_stream(value):
        raise ValueError(
            "Not an encoded stream (missing '-stream/' or '^'): %r"
            % (value[:60] if isinstance(value, str) else value))

    prefix, _, payload = value.partition("^")
    head, _, encoding = prefix.partition(":")
    dtype_part, _, compression = head.partition("/")
    dtype, _, suffix = dtype_part.partition("-")
    if suffix != "stream":
        raise ValueError(
            "Unsupported stream marker %r (expected '<DTYPE>-stream')"
            % dtype_part)

    if dtype not in _DTYPES:
        raise ValueError("Unsupported dtype %r" % dtype)
    fmt_char, item_size = _DTYPES[dtype]

    raw = _decode_encoding(encoding, payload)
    raw = _decompress(compression, raw)

    if len(raw) % item_size != 0:
        raise ValueError(
            "Decoded byte length %d is not a multiple of %d (%s)"
            % (len(raw), item_size, dtype))

    count = len(raw) // item_size
    fmt = "<" + (fmt_char[1:] * count) if fmt_char[0] == "<" \
        else ">" + (fmt_char[1:] * count)
    return list(struct.unpack(fmt, raw))


class YumizenFloatleParseError(ValueError):
    """Raised when a Yumizen FLOATLE stream does not match the
    documented framing."""


def parse_yumizen_floatle(stream, with_scale_ticks=False):
    """Parse a decoded Yumizen FLOATLE stream into its structured
    fields.

    Both the `Thresholds` field (14.6) and the `Points` field (14.7)
    of every Yumizen HISTOGRAM and MATRIX `M` record start with the
    same 4-float display-bounds prefix, followed by either a list
    block (Thresholds) or the same list block preceded by optional
    X / Y scale-tick arrays (Points). The layout is documented in
    section 3.5 of the
    `Yumizen H500 Output Format for Host Connection` spec (filed at
    `instruments/specs/horiba/Yumizen-H500-Comm-Spec.pdf`):

        4f          x_min, x_max, y_min, y_max
        --- only when `with_scale_ticks` is True (Points field) ---
        1f          x_scale_nb
        Nf          x_ticks                (N = x_scale_nb)
        1f          y_scale_nb
        Mf          y_ticks                (M = y_scale_nb)
        --- always ---
        1f          number_of_list
        1f          list_length            (= L; may be 0)
        L*K floats  K parallel lists of L floats
                    (K = number_of_list)

    Treating the stream as a flat array — as a generic plotter
    would — picks up the header floats as the first few "bin
    values" and ends up plotting them as data, which is what made
    SENAITE-side renderings disagree with the vendor printer.

    The semantic meaning of each parallel list depends on context
    (HISTOGRAM Points has `X[], Y[]`; MATRIX Points has
    `X[], Y[], Qty[], Pop[]`); this generic parser surfaces them
    positionally as `lists` and leaves the naming to the
    instrument module (see
    :mod:`senaite.astm.instruments.horiba_yumizen_h5xx`).

    :param stream: list of floats from :func:`decode_stream` (or
        anything else — None / short / wrong types return None so
        callers can fall back to the raw stream).
    :param with_scale_ticks: True for the Points field (14.7),
        False for the Thresholds field (14.6). The Thresholds
        variant omits the X and Y scale-tick arrays — the parser
        would otherwise misread NumberOfList as `x_scale_nb` and
        chase the wrong layout.
    :returns: dict with keys `x_min`, `x_max`, `y_min`, `y_max`,
        `x_ticks` (list, empty when `with_scale_ticks` is False),
        `y_ticks` (list, ditto), `number_of_list` (int),
        `list_length` (int), `lists` (list of `number_of_list`
        lists, each `list_length` floats long). Returns `None`
        when the stream is too short or non-numeric to be
        parseable.
    :raises YumizenFloatleParseError: when the framing reads as
        plausible numbers but the declared sizes do not add up to
        the stream length — the only way to surface a genuine
        format mismatch (e.g. a future firmware variant we don't
        understand yet) without silently dropping data.
    """
    if not isinstance(stream, list) or len(stream) < 6:
        return None
    if not all(isinstance(v, (int, float))
               and not isinstance(v, bool) for v in stream[:6]):
        return None

    x_min, x_max, y_min, y_max = stream[0:4]
    pos = 4

    if with_scale_ticks:
        x_scale_nb = _read_count(stream, pos, "x_scale_nb")
        pos += 1
        x_ticks = stream[pos:pos + x_scale_nb]
        if len(x_ticks) != x_scale_nb:
            raise YumizenFloatleParseError(
                "x_ticks: expected %d, got %d"
                % (x_scale_nb, len(x_ticks)))
        pos += x_scale_nb

        y_scale_nb = _read_count(stream, pos, "y_scale_nb")
        pos += 1
        y_ticks = stream[pos:pos + y_scale_nb]
        if len(y_ticks) != y_scale_nb:
            raise YumizenFloatleParseError(
                "y_ticks: expected %d, got %d"
                % (y_scale_nb, len(y_ticks)))
        pos += y_scale_nb
    else:
        x_ticks = []
        y_ticks = []

    number_of_list = _read_count(stream, pos, "number_of_list")
    pos += 1
    list_length = _read_count(stream, pos, "list_length")
    pos += 1

    expected_tail = number_of_list * list_length
    if len(stream) - pos != expected_tail:
        raise YumizenFloatleParseError(
            "lists tail: expected %d floats (%d lists x %d), "
            "got %d (stream length %d, header consumed %d)"
            % (expected_tail, number_of_list, list_length,
               len(stream) - pos, len(stream), pos))

    lists = []
    for _ in range(number_of_list):
        lists.append(stream[pos:pos + list_length])
        pos += list_length

    return {
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
        "x_ticks": x_ticks,
        "y_ticks": y_ticks,
        "number_of_list": number_of_list,
        "list_length": list_length,
        "lists": lists,
    }


def _read_count(stream, pos, name):
    """Read a count field (declared as FLOATLE in the spec but
    always an integer) and validate it is non-negative."""
    if pos >= len(stream):
        raise YumizenFloatleParseError(
            "%s: stream ended at offset %d" % (name, pos))
    raw = stream[pos]
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        raise YumizenFloatleParseError(
            "%s: expected number at offset %d, got %r"
            % (name, pos, raw))
    count = int(raw)
    if count < 0 or count != raw:
        raise YumizenFloatleParseError(
            "%s: expected non-negative integer, got %r" % (name, raw))
    return count


def _decode_encoding(encoding, payload):
    if encoding == "base64":
        try:
            return base64.b64decode(payload)
        except Exception as exc:
            raise ValueError(
                "base64 decode failed: %s" % exc)
    raise ValueError("Unsupported encoding %r" % encoding)


def _decompress(compression, data):
    if compression == "deflate":
        # The Yumizen emits raw deflate (RFC 1951) — no zlib header,
        # no checksum. Negative window bits tell zlib to skip the
        # header check. Fall back to plain decompress for instruments
        # that wrap their deflate stream in the standard zlib header.
        try:
            return zlib.decompress(data, -zlib.MAX_WBITS)
        except zlib.error:
            try:
                return zlib.decompress(data)
            except zlib.error as exc:
                raise ValueError(
                    "deflate decompression failed: %s" % exc)
    if compression == "gzip":
        try:
            return zlib.decompress(data, zlib.MAX_WBITS | 16)
        except zlib.error as exc:
            raise ValueError(
                "gzip decompression failed: %s" % exc)
    if compression == "":
        return data
    raise ValueError("Unsupported compression %r" % compression)
