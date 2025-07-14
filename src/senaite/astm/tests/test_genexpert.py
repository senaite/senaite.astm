# -*- coding: utf-8 -*-

from senaite.astm import codec
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.instruments import genexpert
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.wrapper import Wrapper
from unittest.mock import MagicMock
from unittest.mock import Mock


class GeneXpert(ASTMTestBase):
    """Test ASTM communication protocol for the Cepheid GeneXpert, a family of
    automated, cartridge-based nucleic acid amplification test (NAAT) systems,
    primarily used for rapid and accurate diagnosis of infectious diseases,
    including tuberculosis.
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

        # read instrument file
        path = self.get_instrument_file_path("genexpert.txt")
        self.lines = self.read_file_lines(path)

        # Mock transport and protocol objects
        self.transport = self.get_mock_transport()
        self.protocol.transport = self.transport
        self.mapping = genexpert.get_mapping()

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

    def test_genexpert_header_record(self):
        """Test the Header Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["H"][0]

        self.assertEqual(record["message_id"], "URM-8lT4abZA-06")
        self.assertEqual(record["sender"]["id"], ".806149 Happy Hospital")
        self.assertEqual(record["sender"]["name"], "GeneXpert")
        self.assertEqual(record["sender"]["software_version"], "4.8")
        self.assertEqual(record["receiver"], "HNH-SENAITE")
        self.assertEqual(record["version"], "1394-97")
        self.assertEqual(record["processing_id"], "P")

    def test_genexpert_order_record(self):
        """Test the Order Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        record = data["O"][0]

        self.assertEqual(record["sample_id"], "PR25A137"),
        self.assertEqual(record["priority"], "R")
        self.assertEqual(record["biomaterial"], "ORH")
        self.assertEqual(record["action_code"], None)
        self.assertEqual(record["report_type"], "F")

    def test_genexpert_result_records(self):
        """Test the Result Record wrapper
        """
        wrapper = Wrapper(self.lines)
        data = wrapper.to_dict()
        records = data["R"]

        # The system can upload three levels of results:
        # • Test result (Main result) identified by the test code followed by
        # • Analyte results (Secondary results for each analyte in the test)
        #   followed by
        # • Complementary results (results related to each analyte) like the
        #   Ct, EndPt, etc.

        # Test Result (Main result)
        rec = records[0]
        self.assertEqual(rec["type"], "R")
        self.assertEqual(rec["seq"], "1")
        self.assertEqual(rec["test"]["panel_id"], "MTB-RIF")
        self.assertEqual(rec["test"]["test_id"], "Xpert")
        self.assertEqual(rec["test"]["test_name"], "Xpert MTB-RIF Ultra")
        self.assertEqual(rec["test"]["test_version"], "4")
        self.assertEqual(rec["test"]["analyte_name"], "MTB")
        self.assertEqual(rec["test"]["complementary_name"], None)
        self.assertEqual(rec["value"]["qualitative_result"], "NOT DETECTED")
        self.assertEqual(rec["value"]["quantitative_result"], None)
        self.assertEqual(rec["units"], None)
        self.assertEqual(rec["references"], None)
        self.assertEqual(rec["abnormal_flag"], None)
        self.assertEqual(rec["status"], "F")
        self.assertEqual(rec["operator"], "John Doe")
        self.assertEqual(rec["started_at"], "20250514121638")
        self.assertEqual(rec["completed_at"], "20250514132103")
        self.assertEqual(rec["instrument"]["system_name"], "Cepheid-44413S0")
        self.assertEqual(rec["instrument"]["instrument_sn"], "806149")
        self.assertEqual(rec["instrument"]["module_sn"], "653624")
        self.assertEqual(rec["instrument"]["cartridge"], "831583371")
        self.assertEqual(rec["instrument"]["reagent_lot"], "56401")
        self.assertEqual(rec["instrument"]["expiration_date"], "20250525")

        # Analyte Result (Secondary result) - MTB-RIF, rpoB1
        rec = records[1]
        self.assertEqual(rec["type"], "R")
        self.assertEqual(rec["seq"], "2")
        self.assertEqual(rec["test"]["panel_id"], "MTB-RIF")
        self.assertEqual(rec["test"]["test_id"], "Xpert")
        self.assertEqual(rec["test"]["test_name"], None)
        self.assertEqual(rec["test"]["test_version"], None)
        self.assertEqual(rec["test"]["analyte_name"], "rpoB1")
        self.assertEqual(rec["test"]["complementary_name"], None)
        self.assertEqual(rec["value"]["qualitative_result"], "INVALID")
        self.assertEqual(rec["value"]["quantitative_result"], None)
        self.assertEqual(rec["units"], None)
        self.assertEqual(rec["references"], None)
        self.assertEqual(rec["abnormal_flag"], None)
        self.assertEqual(rec["status"], None)
        self.assertEqual(rec["operator"], None)
        self.assertEqual(rec["started_at"], None)
        self.assertEqual(rec["completed_at"], None)
        self.assertEqual(rec["instrument"]["system_name"], None)
        self.assertEqual(rec["instrument"]["instrument_sn"], None)
        self.assertEqual(rec["instrument"]["module_sn"], None)
        self.assertEqual(rec["instrument"]["cartridge"], None)
        self.assertEqual(rec["instrument"]["reagent_lot"], None)
        self.assertEqual(rec["instrument"]["expiration_date"], None)

        # Complementary result - MTB-RIF, rpoB1, Ct
        rec = records[2]
        self.assertEqual(rec["type"], "R")
        self.assertEqual(rec["seq"], "3")
        self.assertEqual(rec["test"]["panel_id"], "MTB-RIF")
        self.assertEqual(rec["test"]["test_id"], "Xpert")
        self.assertEqual(rec["test"]["test_name"], None)
        self.assertEqual(rec["test"]["test_version"], None)
        self.assertEqual(rec["test"]["analyte_name"], "rpoB1")
        self.assertEqual(rec["test"]["complementary_name"], "Ct")
        self.assertEqual(rec["value"]["qualitative_result"], None)
        self.assertEqual(rec["value"]["quantitative_result"], "0.0")
        self.assertEqual(rec["units"], None)
        self.assertEqual(rec["references"], None)
        self.assertEqual(rec["abnormal_flag"], None)
        self.assertEqual(rec["status"], None)
        self.assertEqual(rec["operator"], None)
        self.assertEqual(rec["started_at"], None)
        self.assertEqual(rec["completed_at"], None)
        self.assertEqual(rec["instrument"]["system_name"], None)
        self.assertEqual(rec["instrument"]["instrument_sn"], None)
        self.assertEqual(rec["instrument"]["module_sn"], None)
        self.assertEqual(rec["instrument"]["cartridge"], None)
        self.assertEqual(rec["instrument"]["reagent_lot"], None)
        self.assertEqual(rec["instrument"]["expiration_date"], None)

        # Test Result (Main result)
        rec = records[38]
        self.assertEqual(rec["type"], "R")
        self.assertEqual(rec["seq"], "39")
        self.assertEqual(rec["test"]["panel_id"], "MTB-RIF")
        self.assertEqual(rec["test"]["test_id"], "RIF")
        self.assertEqual(rec["test"]["test_name"], "Xpert MTB-RIF Ultra")
        self.assertEqual(rec["test"]["test_version"], "4")
        self.assertEqual(rec["test"]["analyte_name"], "RIF Resistance")
        self.assertEqual(rec["test"]["complementary_name"], None)
        self.assertEqual(rec["value"]["qualitative_result"], None)
        self.assertEqual(rec["value"]["quantitative_result"], None)
        self.assertEqual(rec["units"], None)
        self.assertEqual(rec["references"], None)
        self.assertEqual(rec["abnormal_flag"], None)
        self.assertEqual(rec["status"], "F")
        self.assertEqual(rec["operator"], "John Doe")
        self.assertEqual(rec["started_at"], "20250514121638")
        self.assertEqual(rec["completed_at"], "20250514132103")
        self.assertEqual(rec["instrument"]["system_name"], "Cepheid-44413S0")
        self.assertEqual(rec["instrument"]["instrument_sn"], "806149")
        self.assertEqual(rec["instrument"]["module_sn"], "653624")
        self.assertEqual(rec["instrument"]["cartridge"], "831583371")
        self.assertEqual(rec["instrument"]["reagent_lot"], "56401")
        self.assertEqual(rec["instrument"]["expiration_date"], "20250525")

        # Analyte Result (Secondary result) - MTB-RIF, rpoB1
        rec = records[39]
        self.assertEqual(rec["type"], "R")
        self.assertEqual(rec["seq"], "40")
        self.assertEqual(rec["test"]["panel_id"], "MTB-RIF")
        self.assertEqual(rec["test"]["test_id"], "RIF")
        self.assertEqual(rec["test"]["test_name"], None)
        self.assertEqual(rec["test"]["test_version"], None)
        self.assertEqual(rec["test"]["analyte_name"], "rpoB1")
        self.assertEqual(rec["test"]["complementary_name"], None)
        self.assertEqual(rec["value"]["qualitative_result"], "INVALID")
        self.assertEqual(rec["value"]["quantitative_result"], None)
        self.assertEqual(rec["units"], None)
        self.assertEqual(rec["references"], None)
        self.assertEqual(rec["abnormal_flag"], None)
        self.assertEqual(rec["status"], None)
        self.assertEqual(rec["operator"], None)
        self.assertEqual(rec["started_at"], None)
        self.assertEqual(rec["completed_at"], None)
        self.assertEqual(rec["instrument"]["system_name"], None)
        self.assertEqual(rec["instrument"]["instrument_sn"], None)
        self.assertEqual(rec["instrument"]["module_sn"], None)
        self.assertEqual(rec["instrument"]["cartridge"], None)
        self.assertEqual(rec["instrument"]["reagent_lot"], None)
        self.assertEqual(rec["instrument"]["expiration_date"], None)

        # Complementary result - MTB-RIF, rpoB1, Ct
        rec = records[40]
        self.assertEqual(rec["type"], "R")
        self.assertEqual(rec["seq"], "41")
        self.assertEqual(rec["test"]["panel_id"], "MTB-RIF")
        self.assertEqual(rec["test"]["test_id"], "RIF")
        self.assertEqual(rec["test"]["test_name"], None)
        self.assertEqual(rec["test"]["test_version"], None)
        self.assertEqual(rec["test"]["analyte_name"], "rpoB1")
        self.assertEqual(rec["test"]["complementary_name"], "Ct")
        self.assertEqual(rec["value"]["qualitative_result"], None)
        self.assertEqual(rec["value"]["quantitative_result"], "0.0")
        self.assertEqual(rec["units"], None)
        self.assertEqual(rec["references"], None)
        self.assertEqual(rec["abnormal_flag"], None)
        self.assertEqual(rec["status"], None)
        self.assertEqual(rec["operator"], None)
        self.assertEqual(rec["started_at"], None)
        self.assertEqual(rec["completed_at"], None)
        self.assertEqual(rec["instrument"]["system_name"], None)
        self.assertEqual(rec["instrument"]["instrument_sn"], None)
        self.assertEqual(rec["instrument"]["module_sn"], None)
        self.assertEqual(rec["instrument"]["cartridge"], None)
        self.assertEqual(rec["instrument"]["reagent_lot"], None)
        self.assertEqual(rec["instrument"]["expiration_date"], None)
