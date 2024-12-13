# -*- coding: utf-8 -*-

from unittest.mock import MagicMock
from unittest.mock import Mock

from senaite.astm import codec
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.instruments import abbott_afinion2
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.wrapper import Wrapper


class AbbottAfinion2(ASTMTestBase):
    """Test ASTM communication protocol for the Abbott Afinion™ 2 Analyzer, a
    compact, rapid, multi-assay analyzer that provides valuable near patient
    testing at the point of care.
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

        # read instrument file
        path = self.get_instrument_file_path("abbott_afinion2.txt")
        self.lines = self.read_file_lines(path)

        # Mock transport and protocol objects
        self.transport = self.get_mock_transport()
        self.protocol.transport = self.transport
        self.mapping = abbott_afinion2.get_mapping()

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

    def test_afinion2_header_record(self):
        """Test the Header Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["H"][0]

        # test sender name
        self.assertEqual(record["sender"]["name"], "Afinion 2 Analyzer")
        # test device id (serial)
        self.assertEqual(record["sender"]["serial"], "AF20052397")

        # test processing ID
        self.assertEqual(record["processing_id"], "P")
        # test astm version number
        self.assertEqual(record["version"], "1")

    def test_afinion2_patient_record(self):
        """Test the Patient Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["P"][0]

        # test (local) patient ID
        self.assertEqual(record["laboratory_id"], "3643")

    def test_afinion2_order_record(self):
        """Test the Order Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["O"][0]

        # test filler order number
        self.assertEqual(record["instrument"], "5")

        # test name of assay
        self.assertEqual(record["test"]["name"], "HbA1c")

        # test specimen action code
        self.assertEqual(record["action_code"], "N")

        # test specimen source
        self.assertEqual(record["biomaterial"]["source"], "O")

    def test_afinion2_result_records(self):
        """Test the Result Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        records = data["R"]

        # we should have 1 result
        self.assertEqual(len(records), 1)

        self.assertEqual(records[0]["test"]["name"], "HbA1c")
        self.assertEqual(records[0]["value"], "5.9"),
        self.assertEqual(records[0]["units"], "%")
        self.assertEqual(records[0]["abnormal_flag"], None)
        self.assertEqual(records[0]["status"], "F")
        self.assertEqual(records[0]["operator"], "3643")
