# -*- coding: utf-8 -*-
"""The delimiters an analyzer declares, and the escape sequences it sends

ASTM E1394 fixes the four delimiters in field 2 of the (H)eader record, and
they hold until the (L) record. Every shape asserted here was taken from
captured traffic; the comment above each one says which analyzer sends it
and how often it was seen across two sites.
"""

from unittest import TestCase

from senaite.astm import codec
from senaite.astm.codec import DEFAULT_DELIMITERS
from senaite.astm.codec import Delimiters

#: What a GeneXpert declares. Seen in 76,223 of 76,223 of its messages.
GENEXPERT = Delimiters(b"|", b"@", b"^", b"\\")


class GetDelimiters(TestCase):
    """Reading the declaration out of an (H)eader record"""

    def test_default_declaration(self):
        header = b"H|\\^&|||H7600^1|||||host|RSUPL^REAL|P|1"
        self.assertEqual(codec.get_delimiters(header), DEFAULT_DELIMITERS)

    def test_genexpert_declaration(self):
        header = (b"H|@^\\|GXM-73805556054||GeneXpert PC^GeneXpert^6.4"
                  b"|||||SENAITE||P|1394-97|20251105152033")
        self.assertEqual(codec.get_delimiters(header), GENEXPERT)

    def test_non_header_keeps_the_defaults(self):
        self.assertEqual(
            codec.get_delimiters(b"R|1|^^^989/|131|mmol/l"),
            DEFAULT_DELIMITERS)

    def test_too_short_keeps_the_defaults(self):
        self.assertEqual(codec.get_delimiters(b"H|\\^"), DEFAULT_DELIMITERS)

    def test_malformed_declaration_keeps_the_defaults(self):
        """A definition that is not exactly three characters long is not a
        declaration. Letting it through would decode every field with
        delimiters the analyzer never meant
        """
        self.assertEqual(
            codec.get_delimiters(b"H|\\\\^&|||miniVidas^biomerieux^1.0.0"),
            DEFAULT_DELIMITERS)

    def test_repeated_characters_keep_the_defaults(self):
        self.assertEqual(
            codec.get_delimiters(b"H|^^&|||Something^1.0"), DEFAULT_DELIMITERS)

    def test_bytes_are_required(self):
        with self.assertRaises(TypeError):
            codec.get_delimiters("H|\\^&|")


class Unescape(TestCase):
    """Resolving escape sequences, with the delimiters of the transmission"""

    def test_delimiter_sequences_with_the_defaults(self):
        for code, expected in [(b"F", b"|"), (b"S", b"^"),
                               (b"R", b"\\"), (b"E", b"&")]:
            self.assertEqual(
                codec.unescape(b"a&" + code + b"&b", DEFAULT_DELIMITERS),
                b"a" + expected + b"b")

    def test_delimiter_sequences_with_the_genexpert_delimiters(self):
        """The same four sequences stand for this analyzer's own delimiters,
        and the escape character itself is `\\` rather than `&`
        """
        for code, expected in [(b"F", b"|"), (b"S", b"^"),
                               (b"R", b"@"), (b"E", b"\\")]:
            self.assertEqual(
                codec.unescape(b"a\\" + code + b"\\b", GENEXPERT),
                b"a" + expected + b"b")

    def test_hex_sequence(self):
        """A Hitachi H7600 escapes the `/` of a sample number this way.
        Seen 20 times
        """
        self.assertEqual(
            codec.unescape(b"4175/C11-306 &X2F&L11-893", DEFAULT_DELIMITERS),
            b"4175/C11-306 /L11-893")

    def test_hex_sequence_of_several_bytes(self):
        self.assertEqual(
            codec.unescape(b"a&X0D0A&b", DEFAULT_DELIMITERS), b"a\r\nb")

    def test_malformed_hex_sequence_travels_on(self):
        """Not something to lose a message over"""
        self.assertEqual(
            codec.unescape(b"a&XZZ&b", DEFAULT_DELIMITERS), b"a&XZZ&b")

    def test_unknown_sequence_travels_on(self):
        """`&H&` and `&N&` are the highlighting sequences, and an analyzer
        may define its own. None of them means anything here
        """
        self.assertEqual(
            codec.unescape(b"a&H&b", DEFAULT_DELIMITERS), b"a&H&b")

    def test_an_ampersand_is_literal_for_the_genexpert(self):
        """`&` is an ordinary character when the escape delimiter is `\\`"""
        self.assertEqual(codec.unescape(b"O&G", GENEXPERT), b"O&G")

    def test_value_without_escapes_is_untouched(self):
        self.assertEqual(
            codec.unescape(b"NOT DETECTED", DEFAULT_DELIMITERS),
            b"NOT DETECTED")


class DecodeWithDeclaredDelimiters(TestCase):
    """Whole records, as the analyzers send them"""

    def test_genexpert_repeat(self):
        """`O@N` is two values. Read with the ASTM default `\\` it is one.
        Seen in 59,732 messages
        """
        record = b"Q|1|ALL||||||||||O@N"
        self.assertEqual(
            codec.decode_record(record, delimiters=GENEXPERT)[-1],
            [["O"], ["N"]])
        self.assertEqual(codec.decode_record(record)[-1], "O@N")

    def test_sysmex_scattergram_path(self):
        """`&R&` stands for the repeat delimiter, which this analyzer uses as
        the separator of a file path. Seen 57,258 times
        """
        record = (b"R|45|^^^^SCAT_WDF|PNG&R&20260814&R&2026_08_14_WDF.PNG"
                  b"|||N||F")
        decoded = codec.decode_record(record)
        self.assertEqual(decoded[3], "PNG\\20260814\\2026_08_14_WDF.PNG")

    def test_sysmex_ward_name(self):
        """`O&E&G` is the ward `O&G`, with the `&` escaped. Seen 4 times"""
        record = b"P|1|||12241647|||||||||||||||||||||||^^^O&E&G"
        decoded = codec.decode_record(record)
        self.assertEqual(decoded[-1], [None, None, None, "O&G"])

    def test_header_delimiter_field_is_kept_raw(self):
        """Splitting field 2 with the delimiters it declares is circular,
        so it travels through intact. Before this, `HeaderRecord.delimeter`
        was a workaround that only ever produced something sensible for the
        default `\\^&`
        """
        header = b"H|@^\\|GXM-1||GeneXpert PC^GeneXpert^6.4|||||SENAITE"
        self.assertEqual(
            codec.decode_record(header, delimiters=GENEXPERT)[1], "@^\\")

        header = b"H|\\^&|||H7600^1|||||host"
        self.assertEqual(codec.decode_record(header)[1], "\\^&")

    def test_default_delimiters_are_unchanged_for_everything_else(self):
        record = b"R|1|^^^989/|131|mmol/l||L||F|||||ISE1"
        self.assertEqual(
            codec.decode_record(record),
            ["R", "1", [None, None, None, "989/"], "131", "mmol/l", None,
             "L", None, "F", None, None, None, None, "ISE1"])
