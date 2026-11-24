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
from senaite.astm.encoded_streams import parse_yumizen_floatle
from senaite.astm.encoded_streams import YumizenFloatleParseError


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


class ParseYumizenFloatleTest(unittest.TestCase):
    """The Yumizen H500/H550 frames its Thresholds and Points
    FLOATLE streams as documented in section 3.5 of the H500
    Communication Spec (filed at
    `instruments/specs/horiba/Yumizen-H500-Comm-Spec.pdf`).
    Parsing the structured framing is the only way to plot the
    same curve the vendor's own printer produces — a generic
    flat-array plotter reads the display bounds and scale ticks
    as the first few "bin values"."""

    def test_thresholds_layout_no_scale_ticks(self):
        # 6-float header followed by 2 lists of length 3.
        # NumberOfList = 2, ListLength = 3 ->
        # X = [50, 100, 150], ThrsID = [0, 1, 2].
        stream = [
            0.0, 200.0, 0.0, 100.0,    # display bounds
            2.0, 3.0,                  # NumberOfList=2, ListLength=3
            50.0, 100.0, 150.0,        # X
            0.0, 1.0, 2.0,             # ThrsID
        ]
        out = parse_yumizen_floatle(stream)
        self.assertEqual(out["x_min"], 0.0)
        self.assertEqual(out["x_max"], 200.0)
        self.assertEqual(out["y_min"], 0.0)
        self.assertEqual(out["y_max"], 100.0)
        self.assertEqual(out["x_ticks"], [])
        self.assertEqual(out["y_ticks"], [])
        self.assertEqual(out["number_of_list"], 2)
        self.assertEqual(out["list_length"], 3)
        self.assertEqual(out["lists"],
                         [[50.0, 100.0, 150.0], [0.0, 1.0, 2.0]])

    def test_points_layout_with_scale_ticks(self):
        # Points field carries X and Y scale-tick arrays between
        # the display bounds and NumberOfList.
        stream = [
            0.0, 278.0, 0.0, 700.0,     # bounds
            3.0, 50.0, 100.0, 150.0,    # x_scale_nb=3 + 3 ticks
            0.0,                        # y_scale_nb=0
            2.0, 2.0,                   # NumberOfList=2, ListLength=2
            5.0, 6.0,                   # X
            10.0, 20.0,                 # Y
        ]
        out = parse_yumizen_floatle(stream, with_scale_ticks=True)
        self.assertEqual(out["x_ticks"], [50.0, 100.0, 150.0])
        self.assertEqual(out["y_ticks"], [])
        self.assertEqual(out["lists"], [[5.0, 6.0], [10.0, 20.0]])

    def test_matrix_points_four_parallel_lists(self):
        # MATRIX rows pack X, Y, Qty, Pop (NumberOfList = 4).
        # Pop is the population ID per event so the printer can
        # colour the scatter cloud.
        stream = [
            0.0, 2047.0, 0.0, 2047.0,
            0.0, 0.0,             # no X/Y scale ticks for LMNE
            4.0, 2.0,             # NumberOfList=4, ListLength=2
            100.0, 200.0,         # X
            150.0, 250.0,         # Y
            1.0, 1.0,             # Qty
            0.0, 2.0,             # Pop (LYM, NEU)
        ]
        out = parse_yumizen_floatle(stream, with_scale_ticks=True)
        self.assertEqual(out["lists"],
                         [[100.0, 200.0], [150.0, 250.0],
                          [1.0, 1.0], [0.0, 2.0]])

    def test_empty_list_length_is_legal(self):
        # ListLength = 0 is the documented marker for "no data"
        # (matrix thresholds always send this).
        stream = [0.0, 1.0, 0.0, 1.0, 2.0, 0.0]
        out = parse_yumizen_floatle(stream)
        self.assertEqual(out["list_length"], 0)
        self.assertEqual(out["lists"], [[], []])

    def test_short_stream_returns_none(self):
        self.assertIsNone(parse_yumizen_floatle([1.0, 2.0]))

    def test_none_stream_returns_none(self):
        # REAGENT rows leave the field as None.
        self.assertIsNone(parse_yumizen_floatle(None))

    def test_non_numeric_header_returns_none(self):
        self.assertIsNone(
            parse_yumizen_floatle(
                ["not", "a", "header", "here", 0.0, 0.0]))

    def test_inconsistent_tail_raises(self):
        # Declared NumberOfList * ListLength exceeds the stream:
        # do not silently truncate, raise so the operator sees it.
        stream = [
            0.0, 1.0, 0.0, 1.0,
            2.0, 5.0,           # 2 lists of length 5 -> need 10 more
            1.0, 2.0, 3.0,      # only 3 floats follow
        ]
        with self.assertRaises(YumizenFloatleParseError):
            parse_yumizen_floatle(stream)

    def test_fractional_count_raises(self):
        # Counts are stored as FLOATLE but the spec requires them
        # to be whole numbers. A fractional value means we are
        # misaligned in the stream.
        stream = [
            0.0, 1.0, 0.0, 1.0,
            1.5, 0.0,
        ]
        with self.assertRaises(YumizenFloatleParseError):
            parse_yumizen_floatle(stream)

    def test_thresholds_mode_reads_pos_5_as_list_length(self):
        # Regression test for the original bug: passing a 6-float
        # Thresholds stream with the Points reader would consume
        # stream[4] as x_scale_nb and chase the wrong layout.
        stream = [0.0, 1.0, 0.0, 1.0, 2.0, 0.0]
        # Thresholds mode (with_scale_ticks=False) gives 2 empty
        # parallel lists; Points mode would raise on the inferred
        # tail length.
        self.assertEqual(
            parse_yumizen_floatle(
                stream, with_scale_ticks=False)["lists"],
            [[], []])
        with self.assertRaises(YumizenFloatleParseError):
            parse_yumizen_floatle(stream, with_scale_ticks=True)


def test_suite():
    suite = unittest.TestSuite()
    for cls in (IsEncodedStreamTest, DecodeStreamTest,
                EncodedStreamFieldTest, ParseYumizenFloatleTest):
        suite.addTest(unittest.makeSuite(cls))
    return suite
