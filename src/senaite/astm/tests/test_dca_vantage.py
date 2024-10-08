# -*- coding: utf-8 -*-

from unittest.mock import MagicMock
from unittest.mock import Mock

from senaite.astm import codec
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.instruments import dca_vantage
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.wrapper import Wrapper


class DCAVantage(ASTMTestBase):
    """Test ASTM communication protocol for the SIEMENS DCA Vantage® Analyzer,
    a multi-parameter, point-of-care analyzer for monitoring glycemic control
    in people with diabetes and detecting early kidney disease.
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

        # read instrument file
        path = self.get_instrument_file_path("dca_vantage.txt")
        self.lines = self.read_file_lines(path)

        # Mock transport and protocol objects
        self.transport = self.get_mock_transport()
        self.protocol.transport = self.transport
        self.mapping = dca_vantage.get_mapping()

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

    def test_dca_vantage_header_record(self):
        """Test the Header Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["H"][0]

        # test model
        self.assertEqual(record["sender"]["name"], "DCA VANTAGE")

        # test software version
        self.assertEqual(record["sender"]["version"], "04.04.00.00")

        # test serial number
        self.assertEqual(record["sender"]["serial"], "S067337")

        # test processing id
        self.assertEqual(record["processing_id"], "P")

    def test_dca_vantage_order_record(self):
        """Test the Order Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["O"][0]

        # test sample sequence number
        self.assertEqual(record["instrument"]["sample_seq_num"], "660"),

        # test reagent lot number
        self.assertEqual(record["instrument"]["reagent_lot_num"], "0090"),

        # test action code
        self.assertEqual(record["action_code"], None)

        # test report type
        self.assertEqual(record["report_type"], "F")

    def test_dca_vantage_result_records(self):
        """Test the Result Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        records = data["R"]

        # we should have 3 results
        self.assertEqual(len(records), 3)

        # test parameter name
        tests = ["Alb", "Crt", "Ratio"]
        for idx, record in enumerate(records):
            self.assertEqual(record["test"]["parameter"], tests[idx])

        # test results
        results = ["63.7", "230.8", "27.6"]
        for idx, record in enumerate(records):
            self.assertEqual(record.get("value"), results[idx])

        # test units
        units = ["mg/L", "mg/dL", "mg/g"]
        for idx, record in enumerate(records):
            self.assertEqual(record.get("units"), units[idx])

        # test status
        statuses = ["F", "F", "F"]
        for idx, record in enumerate(records):
            self.assertEqual(record.get("status"), statuses[idx])
