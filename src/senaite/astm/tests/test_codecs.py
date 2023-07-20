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

        msg = f("{STX}1A|B|C|D{CR}{ETX}BF")
        self.assertRaises(ValueError, codec.decode_message, msg, "ascii")

        msg = f("1A|B|C|D{CR}{ETX}BF{CRLF}")
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


class ChecksummTestCase(ASTMTestBase):
    """Test checksum generation
    """
    def test_common(self):
        msg = u("1H|\^&|||ABX|||||||P|E1394-97|20220727121551\x0D\x03")
        self.assertEqual(b"58", codec.make_checksum(msg))

    def test_bytes(self):
        msg = u("1H|\^&|||ABX|||||||P|E1394-97|20220727121551\x0D\x03")
        msg = msg.encode("utf8")
        self.assertEqual(b"58", codec.make_checksum(msg))

    def test_string(self):
        msg = "1H|\^&|||ABX|||||||P|E1394-97|20220727121551\x0D\x03"
        self.assertEqual(b"58", codec.make_checksum(msg))

    def test_short(self):
        self.assertEqual(b"02", codec.make_checksum("\x02"))

    def test_instrument_files(self):
        for path in self.instrument_files:
            data = self.read_file_lines(path)
            for line in data:
                frame = line.rstrip(CRLF)[1:-2]
                cs = line.rstrip(CRLF)[-2:]
                self.assertEqual(cs, codec.make_checksum(frame))
