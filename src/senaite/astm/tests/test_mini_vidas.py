# -*- coding: utf-8 -*-

from unittest.mock import MagicMock
from unittest.mock import Mock

from senaite.astm import codec
from senaite.astm.constants import ACK, ENQ
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.wrapper import Wrapper
from senaite.astm.instruments import biomerieux_mini_vidas


class MiniVidas(ASTMTestBase):
    """Test ASTM communication protocol for the Mini VIDAS analyzer
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

        # This is the actual output of the instrument
        path = self.get_instrument_file_path("mini_vidas.txt")
        self.lines = self.read_file_lines(path)

        # Test fixture
        path = self.get_instrument_file_path("mini_vidas_mock.txt")
        self.mocklines = self.read_file_lines(path)

        # Mock transport and protocol objects
        self.transport = self.get_mock_transport()
        self.protocol.transport = self.transport
        self.mapping = biomerieux_mini_vidas.get_mapping()

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
        wrapper = Wrapper(self.mocklines)
        data = wrapper.to_dict()
        record = data["H"][0]

        # test sender name
        self.assertEqual(record["sender"]["name"].strip(), "miniVidas")
        # test sender manufacturer
        self.assertEqual(record["sender"]["manufacturer"], "biomerieux")
        # test sender version
        self.assertEqual(record["sender"]["version"], "1.0.0")

        # test the timestamp
        self.assertEqual(record["timestamp"], "20241025183500")

    def test_patient_records(self):
        """Test the Result Record wrapper
        """
        wrapper = Wrapper(self.mocklines)
        data = wrapper.to_dict()
        records = data["P"]

        self.assertEqual(len(records), 1)
        patient = records[0]
        self.assertEqual(patient.get("name"), "test_patient")

    def test_order_records(self):
        """Test the Result Record wrapper
        """
        wrapper = Wrapper(self.mocklines)
        data = wrapper.to_dict()
        records = data["O"]

        self.assertEqual(len(records), 1)

        order = records[0]

        self.assertEqual(order.get("sample_id"), "Z1G021SCR")
        self.assertEqual(order.get("test"), "Anti-HBc Total II")

    def test_result_records(self):
        """Test the Result Record wrapper
        """
        wrapper = Wrapper(self.mocklines)
        data = wrapper.to_dict()
        records = data["R"]

        self.assertEqual(len(records), 1)

        results = [
            ["HBCT", "0.05"],
        ]
        for idx, record in enumerate(records):
            values = [
                record.get("test"),
                record.get("value"),
            ]
            self.assertEqual(values, results[idx])
