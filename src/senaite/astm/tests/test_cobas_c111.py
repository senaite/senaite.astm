# -*- coding: utf-8 -*-

from unittest.mock import MagicMock
from unittest.mock import Mock

from senaite.astm import codec
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.records import CommentRecord
from senaite.astm.records import HeaderRecord
from senaite.astm.records import OrderRecord
from senaite.astm.records import PatientRecord
from senaite.astm.records import ResultRecord
from senaite.astm.records import TerminatorRecord
from senaite.astm.records import ManufacturerInfoRecord
from senaite.astm.tests.base import ASTMTestBase


class ASTMProtocolTest(ASTMTestBase):
    """Test ASTM Communication Protocol
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

        self.lines = [
            b'\x021H|\\^&|||C111^Roche^c111^4.2.2.1730^1^13147|||||host|RSUPL^REAL|P|1|20230727162028\r\x179B\r\n',
            b'\x022P|1||\r\x174B\r\n',
            b'\x023O|1||T20-10143GA D07^^2||R||||||N|||||||||||20230727162028|||F\r\x17C0\r\n',
            b'\x024R|1|^^^550|95.2|U/L||N||F||$SYS$||20230727162028\r\x17A2\r\n',
            b'\x025C|1|I||I\r\x174F\r\n',
            b'\x026M|1|RR^BM^c111^1|137|137\\136\\430\\421\\414\\409\\590\\615\\656\\691\\719\\744\\763\\776\\786\\795\\942\\998\\1032\\1055\\1071\\1087\\1106\\1121\\1136\\1154\\1168\\1185\\1199\\1219\\1237\\1252\\1271\\1287|0.005564\r\x17AD\r\n',
            b'\x027L|1|N\r\x030A\r\n',
        ]

        # Mock transport and protocol objects
        self.transport = self.get_mock_transport()
        self.protocol.transport = self.transport

        self.wrappers = {
            "H": HeaderRecord,
            "P": PatientRecord,
            "O": OrderRecord,
            "R": ResultRecord,
            "C": CommentRecord,
            "M": ManufacturerInfoRecord,
            "L": TerminatorRecord,
        }

    def get_mock_transport(self, ip="127.0.0.1", port=12345):
        transport = MagicMock()
        transport.get_extra_info = Mock(return_value=(ip, port))
        transport.write = MagicMock()
        return transport

    def test_communication(self):
        """Test common instrument communication """

        # Establish the connection to build setup the environment
        self.protocol.connection_made(self.transport)

        # Send ENQ
        self.protocol.data_received(ENQ)

        for line in self.lines:
            self.protocol.data_received(line)
            # We expect an ACK as response
            self.transport.write.assert_called_with(ACK)

    def test_decode_messages(self):
        # Establish the connection to build setup the environment
        self.protocol.connection_made(self.transport)

        # Send ENQ
        self.protocol.data_received(ENQ)

        for line in self.lines:
            self.protocol.data_received(line)
            records = codec.decode(line)

            self.assertTrue(isinstance(records, list), True)
            self.assertTrue(len(records) > 0, True)

            record = records[0][0]
            rtype = record[0]
            wrapper = self.wrappers[rtype](*record)
