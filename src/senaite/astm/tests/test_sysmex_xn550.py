# -*- coding: utf-8 -*-

from unittest.mock import MagicMock
from unittest.mock import Mock

from senaite.astm import codec
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.instruments import sysmex_xn
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.wrapper import Wrapper


class SysmexXN550(ASTMTestBase):
    """Test ASTM communication protocol for the Sysmex XN-550, a fully
    automated 5-part differential haematology analyser
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

        # read instrument file
        path = self.get_instrument_file_path("sysmex_xn550.txt")
        self.lines = self.read_file_lines(path)

        # Mock transport and protocol objects
        self.transport = self.get_mock_transport()
        self.protocol.transport = self.transport
        self.mapping = sysmex_xn.get_mapping()

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

    def test_xn550_header_record(self):
        """Test the Header Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["H"][0]

        # test sender name
        self.assertEqual(record["sender"]["name"], "XN-550")
        # test sender version
        self.assertEqual(record["sender"]["version"], "00-24")
        # test analyser serial no
        self.assertEqual(record["sender"]["analyser_serial_no"], "22723")
        # test PS code
        self.assertEqual(record["sender"]["ps_code"], "BD634545")

        # test astm version number
        self.assertEqual(record["version"], "E1394-97")

    def test_xn550_patient_record(self):
        """Test the Patient Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["P"][0]

        # test name
        self.assertEqual(record["name"]["first_name"], "Jim")
        self.assertEqual(record["name"]["last_name"], "Brown")

        # test birthdate
        self.assertEqual(record["birthdate"], "19870626")

        # test sex
        self.assertEqual(record["sex"], "M")

        # test physician
        self.assertEqual(record["physician_id"]["physician_name"], "DR.1")

        # Test location/ward
        self.assertEqual(record["location"]["ward"], "WEST")

    def test_xn550_order_record(self):
        """Test the Order Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["O"][0]

        # test sample_id
        self.assertEqual(record["instrument"]["sampler_adaptor_number"], ""),
        self.assertEqual(record["instrument"]["sampler_adaptor_position"], ""),
        self.assertEqual(record["instrument"]["sample_id"].strip(), "27"),
        self.assertEqual(record["instrument"]["sample_id_attr"], "M"),

        # test parameters
        parameters = [
            'WBC', 'RBC', 'HGB', 'HCT', 'MCV', 'MCH', 'MCHC', 'PLT', 'RDW-SD',
            'RDW-CV', 'MPV', 'NEUT#', 'LYMPH#', 'MONO#', 'EO#', 'BASO#',
            'NEUT%', 'LYMPH%', 'MONO%', 'EO%', 'BASO%', 'IG#', 'IG%'
        ]
        for idx, test in enumerate(record["test"]):
            self.assertEqual(test, parameters[idx])

        # test action code
        self.assertEqual(record["action_code"], "N")

        # test report type
        self.assertEqual(record["report_type"], "F")

    def test_xn550_result_records(self):
        """Test the Result Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        records = data["R"]

        # We should have 41 results
        self.assertEqual(len(records), 41)

        results = [
            "8.13", "2.60", "8.0", "22.7", "87.3", "30.8", "35.2", "99",
            "57.4", "12.8", "7.3", "22.1", "0.4", "4.67", "1.04", "0.59",
            "1.80", "0.03", "0.2", "0.02", "47.5", "14.8", "8.1", "", "40",
            "0", "10", "0", "70", "90", "80", "80", "0", "0", "", "",
            "PNG&R&20240628&R&2024_06_27_13_54_27_WDF.PNG",
            "PNG&R&20240628&R&2024_06_27_13_54_27_WDF_CBC.PNG",
            "PNG&R&20240628&R&2024_06_27_13_54_27_RBC.PNG",
            "PNG&R&20240628&R&2024_06_27_13_54_27_PLT.PNG",
        ]

        for idx, record in enumerate(records):
            self.assertEqual(record.get("value"), results[idx])

        units = [
            "10*3/uL", "10*6/uL", "g/dL", "%", "fL", "pg", "g/dL", "10*3/uL",
            "%", "%", "%", "%", "%", "10*3/uL", "10*3/uL", "10*3/uL",
            "10*3/uL", "10*3/uL", "10*3/uL", "%", "10*3/uL", "fL", "%", "fL",
            "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
            "",
        ]

        for idx, record in enumerate(records):
            self.assertEqual(record.get("units"), units[idx])
