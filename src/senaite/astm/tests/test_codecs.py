# -*- coding: utf-8 -*-
#
# Credits to Alexander Shorin:
# https://github.com/kxepal/python-astm/blob/master/astm/tests/test_codecs.py


from senaite.astm import codec
from senaite.astm.constants import CR
from senaite.astm.constants import CRLF
from senaite.astm.constants import ETB
from senaite.astm.constants import ETX
from senaite.astm.constants import LF
from senaite.astm.constants import STX
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.utils import is_chunked_message
from senaite.astm.utils import join


def u(s):
    if isinstance(s, bytes):
        return s.decode("utf-8")
    return s


def f(s, e="utf-8"):
    return u(s).format(STX=u(STX),
                       ETX=u(ETX),
                       ETB=u(ETB),
                       CR=u(CR),
                       LF=u(LF),
                       CRLF=u(CRLF)).encode(e)


class DecodeTestCase(ASTMTestBase):
    """Test generic message/frame/record decoding
    """
    def test_decode_message(self):
        msg = f("{STX}4C|1|I|CONTROL_FAILED^^PLT_ABOVE_TOLERANCE|I{CR}{ETX}D3{CRLF}")
        records = [["C", "1", "I", ["CONTROL_FAILED", None, "PLT_ABOVE_TOLERANCE"], "I"]]
        self.assertEqual(records, codec.decode(msg))

        # test the sub-routine directly
        # -> returns a tuple of (sequence, records, checksum)
        decoded = (4, records, "D3")
        self.assertEqual(decoded, codec.decode_message(msg))

    def test_decode_frame(self):
        msg = f("4C|1|I|CONTROL_FAILED^^PLT_ABOVE_TOLERANCE|I{CR}{ETX}")
        records = [["C", "1", "I", ["CONTROL_FAILED", None, "PLT_ABOVE_TOLERANCE"], "I"]]
        self.assertEqual(records, codec.decode(msg))

    def test_decode_record(self):
        msg = b"A^B^C^^X"
        records = [["A", "B", "C", None, "X"]]
        self.assertEqual(records, codec.decode_record(msg))

    def test_decode_message_with_nonascii(self):
        msg = f("{STX}1Й|Ц|У|К{CR}{ETX}F1{CRLF}", "cp1251")
        res = [[u("Й"), u("Ц"), u("У"), u("К")]]
        self.assertEqual(res, codec.decode(msg, "cp1251"))


class DecodeMessageTestCase(ASTMTestBase):
    """Test message decoding
    """
    def test_decode_message(self):
        msg = f("{STX}1A|B|C|D{CR}{ETX}BF{CRLF}")
        res = (1, [["A", "B", "C", "D"]], "BF")
        self.assertEqual(res, codec.decode_message(msg, "ascii"))

    def test_fail_decome_message_with_wrong_checksum(self):
        msg = f("{STX}1A|B|C|D{CR}{ETX}00{CRLF}")
        self.assertRaises(AssertionError, codec.decode_message, msg, "ascii")

    def test_fail_decode_invalid_message(self):
        msg = f("A|B|C|D")
        self.assertRaises(ValueError, codec.decode_message, msg, "ascii")

        # msg = f("{STX}1A|B|C|D{CR}{ETX}BF")
        # self.assertRaises(ValueError, codec.decode_message, msg, "ascii")

        msg = f("1A|B|C|D{CR}{ETX}BF")
        self.assertRaises(ValueError, codec.decode_message, msg, "ascii")


class DecodeFrameTestCase(ASTMTestBase):
    """Test frame decoding
    """
    def test_fail_decode_without_tail_data(self):
        msg = f("1A|B|C")
        self.assertRaises(ValueError, codec.decode_frame, msg, "ascii")

    def test_fail_decode_without_seq_value(self):
        msg = f("A|B|C|D{CR}{ETX}")
        self.assertRaises(ValueError, codec.decode_frame, msg, "ascii")

    def test_fail_decode_with_invalid_tail(self):
        msg = f("1A|B|C{ETX}")
        self.assertRaises(ValueError, codec.decode_frame, msg, "ascii")


class DecodeRecordTestCase(ASTMTestBase):
    """Test record decoding
    """
    def test_decode(self):
        msg = f("P|1|2776833|||ABC||||||||||||||||||||")
        res = ["P", "1", "2776833", None, None, "ABC"] + [None] * 20
        self.assertEqual(res, codec.decode_record(msg, "ascii"))

    def test_decode_with_components(self):
        msg = f("A|B^C^D^E|F")
        res = ["A", ["B", "C", "D", "E"], "F"]
        self.assertEqual(res, codec.decode_record(msg, "ascii"))

    def test_decode_with_repeated_components(self):
        msg = f("A|B^C\D^E|F")
        res = ["A", [["B", "C"], ["D", "E"]], "F"]
        self.assertEqual(res, codec.decode_record(msg, "ascii"))

    def test_decode_none_values_for_missed_ones(self):
        msg = f("A|||B")
        res = ["A", None, None, "B"]
        self.assertEqual(res, codec.decode_record(msg, "ascii"))

        msg = f("A|B^^C^D^^E|F")
        res = ["A", ["B", None, "C", "D", None, "E"], "F"]
        self.assertEqual(res, codec.decode_record(msg, "ascii"))

    def test_decode_nonascii_chars_as_unicode(self):
        msg = f("привет|мир|!", "utf8")
        res = [u("привет"), u("мир"), "!"]
        self.assertEqual(res, codec.decode_record(msg, "utf8"))


class ChecksumTestCase(ASTMTestBase):
    """Test checksum generation
    """
    def test_common(self):
        msg = u("2P|1|2776833|||王^大^明||||||||||||||||||||\x0D\x03")
        self.assertEqual(b"CF", codec.make_checksum(msg))

    def test_bytes(self):
        msg = u("2P|1|2776833|||王^大^明||||||||||||||||||||\x0D\x03")
        msg = msg.encode("utf8")
        self.assertEqual(b"4B", codec.make_checksum(msg))

    def test_string(self):
        msg = "2P|1|2776833|||王^大^明||||||||||||||||||||\x0D\x03"
        self.assertEqual(b"CF", codec.make_checksum(msg))

    def test_short(self):
        self.assertEqual(b"02", codec.make_checksum("\x02"))

    def test_instrument_files(self):
        """Read all instrument files and validate their checksums
        """
        for path in self.instrument_files:
            data = self.read_file_lines(path)
            for line in data:
                frame = line.rstrip(CRLF)[1:-2]
                cs = line.rstrip(CRLF)[-2:]
                self.assertEqual(cs, codec.make_checksum(frame))


class EncodeTestCase(ASTMTestBase):
    """Test record encoding
    """
    def test_encode(self):
        msg = f("{STX}1A|B|C|D{CR}{ETX}BF{CRLF}")
        seq, data, cs = codec.decode_message(msg)
        self.assertEqual([msg], codec.encode(data))

    def test_encode_message(self):
        msg = f("{STX}1A|B|C|D{CR}{ETX}BF{CRLF}")
        seq, data, cs = codec.decode_message(msg)
        self.assertEqual(msg, codec.encode_message(seq, data))

    def test_encode_record(self):
        msg = b"A|B^C\D^E|F^G|H"
        record = codec.decode_record(msg, "ascii")
        self.assertEqual(msg, codec.encode_record(record))

    def test_encode_record_with_none_and_non_string(self):
        msg = ["foo", None, 0]
        res = b"foo||0"
        self.assertEqual(res, codec.encode_record(msg))

    def test_encode_component(self):
        msg = ["foo", None, 0]
        res = b"foo^^0"
        self.assertEqual(res, codec.encode_component(msg))

    def test_encode_component_strip_tail(self):
        msg = ["A", "B", "", None, ""]
        res = b"A^B"
        self.assertEqual(res, codec.encode_component(msg))

    def test_encode_repeated_component(self):
        msg = [["foo", 1], ["bar", 2], ["baz", 3]]
        res = b"foo^1\\bar^2\\baz^3"
        self.assertEqual(res, codec.encode_repeated_component(msg))

    def test_count_none_fields_as_empty_strings(self):
        self.assertEqual(b"|B|", codec.encode_record([None, "B", None]))

    def test_iter_encoding(self):
        records = [["foo", 1], ["bar", 2], ["baz", 3]]
        res = [f("{STX}1foo|1{CR}{ETX}32{CRLF}"),
               f("{STX}2bar|2{CR}{ETX}25{CRLF}"),
               f("{STX}3baz|3{CR}{ETX}2F{CRLF}")]
        self.assertEqual(res, list(codec.iter_encode(records)))

    def test_frame_number(self):
        records = list(map(list, "ABCDEFGHIJ"))
        res = [f("{STX}1A{CR}{ETX}82{CRLF}"),
               f("{STX}2B{CR}{ETX}84{CRLF}"),
               f("{STX}3C{CR}{ETX}86{CRLF}"),
               f("{STX}4D{CR}{ETX}88{CRLF}"),
               f("{STX}5E{CR}{ETX}8A{CRLF}"),
               f("{STX}6F{CR}{ETX}8C{CRLF}"),
               f("{STX}7G{CR}{ETX}8E{CRLF}"),
               f("{STX}0H{CR}{ETX}88{CRLF}"),
               f("{STX}1I{CR}{ETX}8A{CRLF}"),
               f("{STX}2J{CR}{ETX}8C{CRLF}")]
        self.assertEqual(res, list(codec.iter_encode(records)))


class ChunkedEncodingTestCase(ASTMTestBase):
    """Test chunked messages
    """
    def test_encode_chunky(self):
        recs = [["foo", 1], ["bar", 24], ["baz", [1, 2, 3], "boo"]]
        res = codec.encode(recs, size=14)
        self.assertTrue(isinstance(res, list))
        self.assertEqual(len(res), 4)

        self.assertEqual(res[0], f("{STX}1foo|1{CR}b{ETB}A8{CRLF}"))
        self.assertEqual(len(res[0]), 14)
        self.assertEqual(res[1], f("{STX}2ar|24{CR}b{ETB}6D{CRLF}"))
        self.assertEqual(len(res[1]), 14)
        self.assertEqual(res[2], f("{STX}3az|1^2^{ETB}C0{CRLF}"))
        self.assertEqual(len(res[2]), 14)
        self.assertEqual(res[3], f("{STX}43|boo{CR}{ETX}33{CRLF}"))
        self.assertLessEqual(len(res[3]), 14)

    def test_decode_chunks(self):
        recs = [["foo", 1], ["bar", 24], ["baz", [1, 2, 3], "boo"]]
        res = codec.encode(recs, size=14)
        for item in res:
            codec.decode(item)

    def test_join_chunks(self):
        recs = [["foo", "1"], ["bar", "24"], ["baz", ["1", "2", "3"], "boo"]]
        chunks = codec.encode(recs, size=14)
        msg = join(chunks)
        self.assertEqual(codec.decode(msg), recs)

    def test_encode_as_single_message(self):
        res = codec.encode_message(2, [["A", 0]], "ascii")
        self.assertEqual(f("{STX}2A|0{CR}{ETX}2F{CRLF}"), res)

    def test_is_chunked_message(self):
        msg = f("{STX}2A|0{CR}{ETB}2F{CRLF}")
        self.assertTrue(is_chunked_message(msg))

        msg = f("{STX}2A|0{CR}{ETX}2F{CRLF}")
        self.assertFalse(is_chunked_message(msg))
