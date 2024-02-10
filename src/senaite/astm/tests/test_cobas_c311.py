# -*- coding: utf-8 -*-

from unittest.mock import MagicMock
from unittest.mock import Mock

from senaite.astm import codec
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.instruments import roche_cobas_c311
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.wrapper import Wrapper


class Cobas311Test(ASTMTestBase):
    """Test ASTM Communication Protocol
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

        # read instrument file
        path = self.get_instrument_file_path("cobas_c311.txt")
        self.lines = self.read_file_lines(path)

        # Mock transport and protocol objects
        self.transport = self.get_mock_transport()
        self.protocol.transport = self.transport
        self.mapping = roche_cobas_c311.get_mapping()

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

    def test_c311_header_record(self):
        """Test the message wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["H"][0]

        # test sender name
        self.assertEqual(record["sender"]["name"], "c311")
        # test sender version
        self.assertEqual(record["sender"]["version"], "1")

        # test comments
        self.assertEqual(record["comments"]["meaning_of_message"], "RSUPL")
        self.assertEqual(record["comments"]["mode_of_message"], "REAL")

        # test processing_id
        self.assertEqual(record["processing_id"], "P")

        # test version
        self.assertEqual(record["version"], "1")

    def test_c311_order_record(self):
        """Test the message wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["O"][0]

        # test sample id
        self.assertEqual(record["sample_id"]["sample_total_counter"], "11625")
        self.assertEqual(record["sample_id"]["sample_id"].strip(),
                         "CL-PL-24-0370")
        self.assertEqual(record["sample_id"]["sample_count"], "1")
        self.assertEqual(record["sample_id"]["sample_daily_counter"], "004")

        # test priority
        self.assertEqual(record["priority"], "R")

        # test reported at
        self.assertEqual(record["reported_at"], "20240203132011")

        # test action code
        self.assertEqual(record["action_code"], "N")

        # test speciment descriptor
        self.assertEqual(record["biomaterial"], "SC")

    def test_c311_result_records(self):
        """Test the result records
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        records = data["R"]

        # We should have 7 results
        self.assertEqual(len(records), 7)

        results = ["22.4", "15.0", "4.1", "301", "1.6", "5.85", "34"]

        for idx, record in enumerate(records):
            self.assertEqual(record.get("value"), results[idx])
