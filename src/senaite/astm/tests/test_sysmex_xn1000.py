# -*- coding: utf-8 -*-

from unittest.mock import MagicMock
from unittest.mock import Mock

from senaite.astm import codec
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.instruments import sysmex_xn
from senaite.astm.transports.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.wrapper import Wrapper


class SysmexXN1000(ASTMTestBase):
    """Test ASTM communication protocol for the Sysmex XN-1000.

    The XN-1000 is a system configuration, not an analytical module: the
    header carries the identifier of the measuring hardware inside it,
    `XN-10`, or `XN-20` when the white precursor channel module is fitted.
    The sender name is padded to ten characters.

    Unlike the XN-L series, this analyzer sends one record per frame.
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

        # read instrument file
        path = self.get_instrument_file_path("sysmex_xn1000.txt")
        self.lines = self.read_file_lines(path)

        # Mock transport and protocol objects
        self.transport = self.get_mock_transport()
        self.protocol.transport = self.transport
        self.mapping = sysmex_xn.INSTRUMENT.record_map

    def get_mock_transport(self, ip="127.0.0.1", port=12345):
        transport = MagicMock()
        transport.get_extra_info = Mock(return_value=(ip, port))
        transport.write = MagicMock()
        return transport

    def test_communication(self):
        """Test common instrument communication"""

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

    def test_header_claims_the_instrument(self):
        """The analyzer names the module, not the system, and pads it"""
        wrapper = Wrapper(self.lines)
        self.assertIsInstance(wrapper.instrument, sysmex_xn.SysmexXN)

        record = wrapper.to_dict()["H"][0]
        self.assertEqual(record["sender"]["name"], "     XN-10")
        self.assertEqual(record["sender"]["name"].strip(), "XN-10")
        self.assertEqual(record["sender"]["version"], "00-22")
        self.assertEqual(record["sender"]["serial"], "11111")

    def test_sysmex_xn1000_order_record(self):
        """The sample id travels in the instrument specimen id, padded"""
        wrapper = Wrapper(self.lines)
        record = wrapper.to_dict()["O"][0]

        # the sample id field itself is not used by this analyzer
        self.assertFalse(record["sample_id"])

        instrument = record["instrument"]
        self.assertEqual(instrument["sampler_adaptor_number"], "1")
        self.assertEqual(instrument["sampler_adaptor_position"], "8")
        self.assertEqual(instrument["sample_id"].strip(), "12345")

    def test_sysmex_xn1000_result_records(self):
        """Every result names its parameter and when it was completed"""
        wrapper = Wrapper(self.lines)
        results = wrapper.to_dict()["R"]

        # the analyzer sends one record per reported parameter
        self.assertTrue(len(results) > 1)

        by_parameter = dict(
            [(r["test"]["parameter"], r) for r in results])

        # a measured count
        wbc = by_parameter["WBC"]
        self.assertEqual(wbc["value"], "28.00")
        self.assertEqual(wbc["units"], "10*9/L")
        self.assertEqual(wbc["abnormal_flag"], "H")

        # a differential, reported both as a count and as a percentage
        self.assertIn("NEUT#", by_parameter)
        self.assertIn("NEUT%", by_parameter)

        # and the interpretive messages the analyzer raises, which carry a
        # parameter name but no unit
        self.assertIn("Left_Shift?", by_parameter)
        self.assertEqual(by_parameter["Left_Shift?"]["units"], "")
