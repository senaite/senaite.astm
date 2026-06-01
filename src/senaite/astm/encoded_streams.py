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
