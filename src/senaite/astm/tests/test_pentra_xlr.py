# -*- coding: utf-8 -*-

from unittest.mock import MagicMock
from unittest.mock import Mock

from senaite.astm import codec
from senaite.astm.constants import ACK, ENQ
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.wrapper import Wrapper
from senaite.astm.instruments import horiba_pentra_xlr


class PentraXLR(ASTMTestBase):
    """Test ASTM communication protocol for the Pentra  XLR
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

        # This is the actual output of the instrument
        path = self.get_instrument_file_path("pentra_xlr.txt")
        self.lines = self.read_file_lines(path)

        # Mock transport and protocol objects
        self.transport = self.get_mock_transport()
        self.protocol.transport = self.transport
        self.mapping = horiba_pentra_xlr.get_mapping()

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
        """Test the message wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["H"][0]

        # test sender name
        self.assertEqual(record["sender"], "ABX")

        # test processing_id
        self.assertEqual(record["processing_id"], "P")

        # test the version
        self.assertEqual(record["version"], "E1394-97")

    def test_patient_record(self):
        """Test the message wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["P"][0]

        # test first name / last name
        self.assertEqual(record["name"]["first_name"], "Rita")
        self.assertEqual(record["name"]["name"], "Mohale")

        # test birthdate
        self.assertEqual(record["birthdate"], "19771201")

        # test sex
        self.assertEqual(record["sex"], "F")

    def test_order_record(self):
        """Test the message wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["O"][0]

        # test sample id
        self.assertEqual(record["sample_id"]["id"], "S1234")
        self.assertEqual(record["sample_id"]["rack"], "00")
        self.assertEqual(record["sample_id"]["position"], "00")

        # test testname
        self.assertEqual(record["test"]["testname"], "DIF")

        # test sampled_at
        self.assertEqual(record["sampled_at"], "20220527000000")

        # test sampled_at
        self.assertEqual(record["collected_at"], "20220526000000")

        # test specimen descriptor
        self.assertEqual(record["biomaterial"], "Standard")

    def test_result_records(self):
        """Test the Result Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        records = data["R"]

        self.assertEqual(len(records), 21)

        results = [
            ["WBC",   "804-5", "1", "8.5",   None, "W"],
            ["LYM#",  "731-0", "1", "3.29",  None, "W"],
            ["LYM%",  "736-9", "1", "38.6",  None, "W"],
            ["MON#",  "742-7", "1", "0.15",  "L",  "W"],
            ["MON%",  "744-3", "1", "1.8",   None, "W"],
            ["NEU#",  "751-8", "1", "4.62",  None, "W"],
            ["NEU%",  "770-8", "1", "54.2",  None, "W"],
            ["EOS#",  "711-2", "1", "0.46",  None, "W"],
            ["EOS%",  "713-8", "1", "5.4",   None, "W"],
            ["BAS#",  "704-7", "1", "-----", "HH", "X"],
            ["BAS%",  "706-2", "1", "-----", None, "X"],
            ["RBC",   "789-9", "1", "4.65",  None, "F"],
            ["HGB",   "717-9", "1", "14.0",  None, "F"],
            ["HCT",   "4544-3", "1", "40.9", None, "F"],
            ["MCV",   "787-2", "1", "88",    None, "F"],
            ["MCH",   "785-6", "1", "30.1",  None, "F"],
            ["MCHC",  "786-4", "1", "34.2",  None, "F"],
            ["RDW",   "788-0", "1", "13.5",  None, "F"],
            ["PLT",   "777-3", "1", "234",   None, "F"],
            ["MPV",   "776-5", "1", "10.2",  None, "F"],
            ["RDWSD", "2100-5", "1", "43",   None, "F"],
        ]
        for idx, record in enumerate(records):
            values = [
                record["test"]["result_name"],
                record["test"]["loinc_code"],
                record["test"]["testname"],
                record["value"],
                record["abnormal_flag"],
                record["status"],
            ]
            self.assertEqual(values, results[idx])
