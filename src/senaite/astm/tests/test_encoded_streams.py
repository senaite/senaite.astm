# -*- coding: utf-8 -*-
"""Tests for :mod:`senaite.astm.encoded_streams`.

The decoder is the entry point that turns
`<DTYPE>-stream/<COMPRESSION>:<ENCODING>^<payload>` payloads (as
emitted by Horiba Yumizen HISTOGRAM and MATRIX rows) into plain
Python lists of numeric values. The tests cover the format pieces
the decoder needs to support today plus the error paths.
"""

import base64
import struct
import unittest
import zlib

from senaite.astm.encoded_streams import decode_stream
from senaite.astm.encoded_streams import is_encoded_stream


def _encode(values, dtype="<f", compression="deflate"):
    """Build a `<DTYPE>-stream/<COMPRESSION>:base64^<payload>` value
    for use in tests. `dtype` is a `struct` format prefix; the
    matching dtype tag is derived for the prefix."""
    raw = b"".join(struct.pack(dtype, v) for v in values)
    if compression == "deflate":
        # Raw deflate (RFC 1951) — what the Yumizen emits.
        deflate = zlib.compressobj(-1, zlib.DEFLATED, -zlib.MAX_WBITS)
        payload = deflate.compress(raw) + deflate.flush()
        compression_tag = "deflate"
    elif compression == "":
        payload = raw
        compression_tag = ""
    else:
        raise ValueError("unsupported test compression: %r" % compression)

    dtype_tag = {
        "<f": "FLOATLE", ">f": "FLOATBE",
        "<i": "INT32LE", ">i": "INT32BE",
        "<h": "INT16LE", ">h": "INT16BE",
    }[dtype]

    b64 = base64.b64encode(payload).decode("ascii")
    return "%s-stream/%s:base64^%s" % (dtype_tag, compression_tag, b64)


class IsEncodedStreamTest(unittest.TestCase):

    def test_recognises_yumizen_floatle_stream(self):
        self.assertTrue(is_encoded_stream(
            "FLOATLE-stream/deflate:base64^Y2AAg"))

    def test_rejects_plain_text(self):
        self.assertFalse(is_encoded_stream("HISTOGRAM"))

    def test_rejects_value_without_caret(self):
        self.assertFalse(is_encoded_stream(
            "FLOATLE-stream/deflate:base64"))

    def test_rejects_non_string(self):
        self.assertFalse(is_encoded_stream(None))
        self.assertFalse(is_encoded_stream(["a", "b"]))
        self.assertFalse(is_encoded_stream(42))


class DecodeStreamTest(unittest.TestCase):

    def test_floatle_deflate_round_trip(self):
        values = [0.0, 1.5, -3.25, 1e6, 0.0001]
        encoded = _encode(values, dtype="<f", compression="deflate")
        decoded = decode_stream(encoded)
        self.assertEqual(len(decoded), len(values))
        for got, want in zip(decoded, values):
            self.assertAlmostEqual(got, want, places=3)

    def test_int32le_deflate_round_trip(self):
        values = [0, 1, -1, 65535, -2_147_483_648, 2_147_483_647]
        encoded = _encode(values, dtype="<i", compression="deflate")
        self.assertEqual(decode_stream(encoded), values)

    def test_uncompressed_payload(self):
        values = [1.0, 2.0, 3.0]
        encoded = _encode(values, dtype="<f", compression="")
        self.assertEqual(
            [round(v, 3) for v in decode_stream(encoded)],
            values)

    def test_unsupported_dtype_raises(self):
        with self.assertRaises(ValueError):
            decode_stream("DOUBLE-stream/deflate:base64^anything")

    def test_unsupported_compression_raises(self):
        with self.assertRaises(ValueError):
            decode_stream("FLOATLE-stream/xz:base64^anything")

    def test_unsupported_encoding_raises(self):
        with self.assertRaises(ValueError):
            decode_stream("FLOATLE-stream/deflate:hex^anything")

    def test_malformed_base64_raises(self):
        with self.assertRaises(ValueError):
            decode_stream("FLOATLE-stream/deflate:base64^not_base64!!!")

    def test_non_stream_value_raises(self):
        with self.assertRaises(ValueError):
            decode_stream("just a string")

    def test_byte_count_not_multiple_of_item_size_raises(self):
        # 5 raw bytes is not a clean multiple of 4 (FLOATLE = 4 bytes).
        raw = b"abcde"
        deflate = zlib.compressobj(-1, zlib.DEFLATED, -zlib.MAX_WBITS)
        payload = deflate.compress(raw) + deflate.flush()
        b64 = base64.b64encode(payload).decode("ascii")
        encoded = "FLOATLE-stream/deflate:base64^" + b64
        with self.assertRaises(ValueError):
            decode_stream(encoded)


class EncodedStreamFieldTest(unittest.TestCase):
    """The Yumizen `ManufacturerInfoRecord` uses
    :class:`EncodedStreamField` for `axis_x` / `axis_y`. The codec
    splits the field on `^` into `[prefix, payload]` before it
    reaches us; the field must rejoin and decode them, and pass any
    non-stream value through unchanged (e.g. for REAGENT rows that
    leave these slots empty)."""

    def setUp(self):
        from senaite.astm.fields import EncodedStreamField
        self.field = EncodedStreamField(name="axis_x")

    def test_decodes_split_components(self):
        values = [1.0, 2.0, 3.0]
        encoded = _encode(values, dtype="<f")
        prefix, payload = encoded.split("^", 1)
        decoded = self.field._set_value([prefix, payload])
        self.assertEqual([round(v, 3) for v in decoded], values)

    def test_passes_through_non_stream_value(self):
        # REAGENT records leave axis_x as None; other vendor variants
        # might put a free-text annotation there. Either way the
        # field must not crash.
        self.assertIsNone(self.field._set_value(None))
        self.assertEqual(self.field._set_value("just text"), "just text")
        # Repeated component shape from an unrelated row type:
        rep = [["a", "b"], ["c", "d"]]
        self.assertEqual(self.field._set_value(rep), rep)


def test_suite():
    suite = unittest.TestSuite()
    for cls in (IsEncodedStreamTest, DecodeStreamTest,
                EncodedStreamFieldTest):
        suite.addTest(unittest.makeSuite(cls))
    return suite
