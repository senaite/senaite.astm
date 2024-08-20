# -*- coding: utf-8 -*-

from unittest.mock import MagicMock
from unittest.mock import Mock

from senaite.astm import codec
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.instruments import sysmex_xp
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.wrapper import Wrapper


class SysmexXP100(ASTMTestBase):
    """Test ASTM communication protocol for the Sysmex XP-100, an automated
    3-part differential haematology analyser
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

        # read instrument file
        path = self.get_instrument_file_path("sysmex_xp100.txt")
        self.lines = self.read_file_lines(path)

        # Mock transport and protocol objects
        self.transport = self.get_mock_transport()
        self.protocol.transport = self.transport
        self.mapping = sysmex_xp.get_mapping()

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

    def test_xp100_header_record(self):
        """Test the Header Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["H"][0]

        # test model
        self.assertEqual(record["sender"]["name"], "XP-100")
        # test software version
        self.assertEqual(record["sender"]["version"], "00-13")
        # test device number
        self.assertEqual(record["sender"]["device_number"], "A7869")
        # test PS code
        self.assertEqual(record["sender"]["ps_code"], "BS649542")

        # test astm version number
        self.assertEqual(record["version"], "E1394-97")

    def test_xp100_order_record(self):
        """Test the Order Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["O"][0]

        # test sample_id
        self.assertEqual(record["instrument"]["sample_id"].strip(), "113"),
        self.assertEqual(record["instrument"]["sample_id_attr"], "A"),

        # test parameters
        parameters = [
            "WBC", "RBC", "HGB", "HCT", "MCV", "MCH", "MCHC", "PLT", "LYM%",
            "MXD%", "NEUT%", "LYM#", "MXD#", "NEUT#", "RDW-SD", "RDW-CV",
            "PDW", "MPV", "P-LCR", "PCT"
        ]
        for idx, test in enumerate(record["test"]):
            self.assertEqual(test["parameter"], parameters[idx])

        # test action code
        self.assertEqual(record["action_code"], "N")

        # test report type
        self.assertEqual(record["report_type"], "F")

    def test_xp100_result_records(self):
        """Test the Result Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        records = data["R"]

        # We should have 20 results
        self.assertEqual(len(records), 20)

        results = [
            "  5.5", " 2.87", " 10.1", " 24.2", " 84.3", " 35.2", " 41.7", 
            "  170", " 26.4", " 10.2", " 63.4", "  1.5", "  0.6", "  3.4", 
            " 38.5", " 11.8", " 12.8", " 10.2", " 26.9", " 0.17"
        ]
        for idx, record in enumerate(records):
            self.assertEqual(record.get("value"), results[idx])

        units = [
            "10*3/uL", "10*6/uL", "g/dL", "%", "fL", "pg", "g/dL", "10*3/uL", 
            "%", "%", "%", "10*3/uL", "10*3/uL", "10*3/uL", "fL", "%", "fL", 
            "fL", "%", "%"
        ]
        for idx, record in enumerate(records):
            self.assertEqual(record.get("units"), units[idx])

        flags = [
            "N", "N", "N", "L", "L", "N", "H", "N", "N", "N", "N", "N", "N", 
            "N", "N", "N", "N", "N", "N", "N"
        ]
        for idx, record in enumerate(records):
            self.assertEqual(record.get("abnormal_flag"), flags[idx])
