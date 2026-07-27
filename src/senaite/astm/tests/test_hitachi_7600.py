# -*- coding: utf-8 -*-

from unittest.mock import MagicMock
from unittest.mock import Mock

from senaite.astm import codec
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.instruments import hitachi_7600
from senaite.astm.transports.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.wrapper import Wrapper


class Hitachi7600Test(ASTMTestBase):
    """Test ASTM Communication Protocol
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

        # read instrument file
        path = self.get_instrument_file_path("hitachi_7600.txt")
        self.lines = self.read_file_lines(path)

        # Mock transport and protocol objects
        self.transport = self.get_mock_transport()
        self.protocol.transport = self.transport
        self.mapping = hitachi_7600.INSTRUMENT.record_map

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

    def test_h7600_header_record(self):
        """Test the message wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["H"][0]

        # test sender name
        self.assertEqual(record["sender"]["name"], "H7600")
        # test sender version
        self.assertEqual(record["sender"]["version"], "1")

        # test comments
        self.assertEqual(record["comments"]["meaning_of_message"], "RSUPL")
        self.assertEqual(record["comments"]["mode_of_message"], "BATCH")

        # test processing_id
        self.assertEqual(record["processing_id"], "P")

        # test version
        self.assertEqual(record["version"], "1")

    def test_h7600_order_record(self):
        """Test the message wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["O"][0]

        # test sample id
        self.assertEqual(record["sample_id"]["sample_total_counter"], "0")
        self.assertEqual(record["sample_id"]["sample_id"].strip(), "6")
        self.assertEqual(record["sample_id"]["sample_count"], "1")
        self.assertEqual(record["sample_id"]["sample_daily_counter"], "006")

        # test priority
        self.assertEqual(record["priority"], "R")

        # test reported at
        self.assertEqual(record["reported_at"], "20260609095815")

        # test action code
        self.assertEqual(record["action_code"], "N")

        # test specimen descriptor
        self.assertEqual(record["biomaterial"], "SC")

    def test_h7600_result_records(self):
        """Test the result records
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        records = data["R"]

        # We should have 22 results
        self.assertEqual(len(records), 22)

        results = [
            "133", "4.44", "97.3", "93", "22.06",
            "34.0", "22.3", "18,2", "2,2", "5,60",
            "210", "1.21", "3.88", "71.8", "6.3",
            "1.58", "262", "8", "2", "1",
            "55", "38"
        ]

        units = [
            "mmol/l", "mmol/l", "mmol/l", "U/l", "mmol/l",
            "g/l", "U/l", "U/l", "umol/l", "mmol/l",
            "U/l", "mmol/l", "mmol/l", "g/l", "umol/l",
            "mmol/l", "umol/l", "", "", "",
            "umol/l", "g/L"
        ]

        for idx, record in enumerate(records):
            self.assertEqual(record.get("value"), results[idx])
            self.assertEqual(record.get("units"), units[idx])
