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
    """Test message decoding
    """

    def test_decode_message(self):
        msg = f("{STX}4C|1|I|CONTROL_FAILED^^PLT_ABOVE_TOLERANCE|I{CR}{ETX}D3{CRLF}")
        res = [['C', '1', 'I', ['CONTROL_FAILED', None, 'PLT_ABOVE_TOLERANCE'], 'I']]
        self.assertEqual(res, codec.decode(msg))

    def test_decode_frame(self):
        msg = f("4C|1|I|CONTROL_FAILED^^PLT_ABOVE_TOLERANCE|I{CR}{ETX}")
        res = [['C', '1', 'I', ['CONTROL_FAILED', None, 'PLT_ABOVE_TOLERANCE'], 'I']]
        self.assertEqual(res, codec.decode(msg))

    def test_decode_message_with_nonascii(self):
        msg = f('{STX}1Й|Ц|У|К{CR}{ETX}F1{CRLF}', 'cp1251')
        res = [[u('Й'), u('Ц'), u('У'), u('К')]]
        self.assertEqual(res, codec.decode(msg, 'cp1251'))


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
