# -*- coding: utf-8 -*-

from unittest.mock import MagicMock
from unittest.mock import Mock

from senaite.astm import codec
from senaite.astm.constants import ACK
from senaite.astm.constants import EOT
from senaite.astm.constants import ENQ
from senaite.astm.instruments import sysmex_xn
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.wrapper import Wrapper
from senaite.astm.instruments import spotchem_el


class SpotchemEL(ASTMTestBase):
    """Test ASTM communication protocol for the Spotchem EL SE-1520
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

        self.lines = [
            b'\x0224/10/29 13:08 ID# 1DC042FP   [B. Plasma] Na       131  mmol/L K        9.7  mmol/L Cl        96  mmol/L              \x03'
        ]

        # Mock transport and protocol objects
        self.transport = self.get_mock_transport()
        self.protocol.transport = self.transport
        self.mapping = spotchem_el.get_mapping()

    def get_mock_transport(self, ip="127.0.0.1", port=12345):
        transport = MagicMock()
        transport.get_extra_info = Mock(return_value=(ip, port))
        transport.write = MagicMock()
        return transport

    def test_communication(self):
        """Test common instrument communication """

        # Establish the connection to build setup the environment
        self.protocol.connection_made(self.transport)

        for line in self.lines:
            self.protocol.data_received(line)
            # We expect an ACK as response
            self.transport.write.assert_called_with(ACK)

    def test_decode_messages(self):
        self.test_communication()

        data = {}
        keys = []

        for line in self.protocol.messages:
            records = codec.decode(line)

            self.assertTrue(isinstance(records, list), True)
            self.assertTrue(len(records) > 0, True)

            record = records[0]
            rtype = record[0]
            wrapper = self.mapping[rtype](*record)
            data[rtype] = wrapper.to_dict()
            keys.append(rtype)

        for key in keys:
            self.assertTrue(key in data)

    def test_header_record(self):
        """Test the Header Record wrapper
        """
        self.test_communication()

        wrapper = Wrapper(self.protocol.messages)
        data = wrapper.to_dict()
        record = data["H"][0]

        # test sender name
        self.assertEqual(record["sender"]["name"].strip(), "SE-1520")
        # test sender manufacturer
        self.assertEqual(record["sender"]["manufacturer"], "Spotchem")
        # test sender version
        self.assertEqual(record["sender"]["version"], "1.0.0")

    def test_xn550_result_records(self):
        """Test the Result Record wrapper
        """
        self.test_communication()

        wrapper = Wrapper(self.protocol.messages)
        data = wrapper.to_dict()
        records = data["R"]

        # We should have 41 results
        self.assertEqual(len(records), 3)

        results = [
            ["Na", "131.0", "mmol/L"],
            ["K", "9.7", "mmol/L"],
            ["Cl", "96.0", "mmol/L"],
        ]
        for idx, record in enumerate(records):
            values = [record.get("test"), record.get("value"), record.get("units")]
            self.assertEqual(values, results[idx])