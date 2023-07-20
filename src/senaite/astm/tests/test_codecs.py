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
