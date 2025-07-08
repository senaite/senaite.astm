# -*- coding: utf-8 -*-

from unittest.mock import MagicMock
from unittest.mock import Mock

from senaite.astm import codec
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.instruments import abbott_architect
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.wrapper import Wrapper


class AbbottArchitect(ASTMTestBase):
    """Test ASTM communication protocol for the Abbott ARCHITECT
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

        # read instrument file
        path = self.get_instrument_file_path("abbott_architect.txt")
        self.lines = self.read_file_lines(path)

        # Mock transport and protocol objects
        self.transport = self.get_mock_transport()
        self.protocol.transport = self.transport
        self.mapping = abbott_architect.get_mapping()

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

    def test_architect_header_record(self):
        """Test the Header Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["H"][0]

        self.assertEqual(record["sender"]["name"], "ARCHITECT")
        self.assertEqual(record["sender"]["version"], "1.00")
        self.assertEqual(record["sender"]["serial"], "123456789")
        self.assertEqual(record["sender"]["interface"], "H1P1O1R1C1Q1L1")
        self.assertEqual(record["processing_id"], "P")
        self.assertEqual(record["version"], "1")

    def test_architect_patient_record(self):
        """Test the Patient Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["P"][0]

        self.assertEqual(record["practice_id"], None)
        self.assertEqual(record["laboratory_id"], None)
        self.assertEqual(record["id"], "PIDSID13")
        self.assertEqual(record["name"]["last"], "Patient")
        self.assertEqual(record["name"]["first"], "Im")
        self.assertEqual(record["name"]["middle"], "A")
        self.assertEqual(record["sex"], "F")
        self.assertEqual(record["physician_id"], "Dr.Amesbury")
        self.assertEqual(record["location"], "ParkClinic")

    def test_architect_order_record(self):
        """Test the Order Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["O"][0]

        self.assertEqual(record["sample_id"], "SID13")
        self.assertEqual(record["instrument"]["specimen"], "SID3")
        self.assertEqual(record["instrument"]["carrier"], "A123")
        self.assertEqual(record["instrument"]["position"], "5")
        self.assertEqual(record["test"]["num"], "123")
        self.assertEqual(record["test"]["name"], "Assay1")
        self.assertEqual(record["test"]["dilution"], "UNDILUTED")
        self.assertEqual(record["test"]["status"], "P")
        self.assertEqual(record["priority"], "R")
        self.assertEqual(record["action_code"], None)
        self.assertEqual(record["report_type"], "F")

    def test_architect_result_records(self):
        """Test the Result Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        records = data["R"]

        # we should have 3 results
        self.assertEqual(len(records), 3)

        self.assertEqual(records[0]["test"]["num"], "21")
        self.assertEqual(records[0]["test"]["name"], "B-hCG")
        self.assertEqual(records[0]["test"]["dilution"], "UNDILUTED")
        self.assertEqual(records[0]["test"]["status"], "P")
        self.assertEqual(records[0]["test"]["reagent_lot"], "47331M100")
        self.assertEqual(records[0]["test"]["reagent_serial"], "00788")
        self.assertEqual(records[0]["test"]["control_lot"], None)
        self.assertEqual(records[0]["test"]["result_type"], "F")
        self.assertEqual(records[0]["value"], "< 1.20"),
        self.assertEqual(records[0]["units"], "mIU/mL")
        self.assertEqual(records[0]["references"], "0.35 TO 4.94")
        abnormal_flags= [{"flag": "EXP"}, {"flag": "<"}]
        self.assertEqual(records[0]["abnormal_flag"], abnormal_flags)
        self.assertEqual(records[0]["status"], "F")
        self.assertEqual(records[0]["instrument"], "I20100")
