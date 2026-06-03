# -*- coding: utf-8 -*-

from unittest.mock import MagicMock
from unittest.mock import Mock

from senaite.astm.constants import ACK
from senaite.astm.constants import CRLF
from senaite.astm.constants import ENQ
from senaite.astm.constants import EOT
from senaite.astm.constants import NAK
from senaite.astm.transports.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase


class ASTMProtocolTest(ASTMTestBase):
    """Test ASTM Communication Protocol
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

    def get_mock_transport(self, ip="127.0.0.1", port=12345):
        transport = MagicMock()
        transport.get_extra_info = Mock(return_value=(ip, port))
        transport.write = MagicMock()
        return transport

    def test_connection_made(self):
        # Mock transport and protocol objects
        transport = self.get_mock_transport()

        # Call connection_made on the protocol
        self.protocol.connection_made(transport)

        # Assert that the transport is set correctly
        self.assertEqual(self.protocol.transport, transport)

    def test_astm_communication(self):
        # Mock transport and protocol objects
        transport = self.get_mock_transport()
        self.protocol.transport = transport

        # Establish the connection to build setup the environment
        self.protocol.connection_made(transport)

        # Check that the protocol is not in transfer state
        self.assertFalse(self.protocol.in_transfer_state)

        # Send ENQ
        self.protocol.data_received(ENQ)

        # We should be now in transfer state
        self.assertTrue(self.protocol.in_transfer_state)

        # We expect an ACK as response
        transport.write.assert_called_with(ACK)

        # Sending ENQ again is not allowed
        self.protocol.data_received(ENQ)

        # The protocol should answer with NAK
        transport.write.assert_called_with(NAK)

        # read instrument file
        path = self.get_instrument_file_path("yumizen_h500.txt")
        lines = self.read_file_lines(path)
        for line in lines:
            # Test fixture: Remove trailing \r\n
            message = line.strip(CRLF)
            self.protocol.data_received(message)
            # We expect an ACK as response
            transport.write.assert_called_with(ACK)

        # all messages (without STX, sequence and checksum) should be
        # collected in the protocol
        self.assertTrue(len(self.protocol.messages) == len(lines))

        # Send EOT
        self.protocol.data_received(EOT)
        # We expect an ACK as response
        transport.write.assert_called_with(ACK)

        # Protocol messages should be flushed
        self.assertTrue(len(self.protocol.messages) == 0)

        # Protocol should be no longer in transfer state
        self.assertFalse(self.protocol.in_transfer_state)

    def test_empty_session_disconnect_logs_at_debug(self):
        """A TCP probe (connect + close, no data) must not fire a
        WARNING — it's routine noise from Zabbix / load balancers."""
        transport = self.get_mock_transport()
        self.protocol.connection_made(transport)

        with self.assertLogs("senaite.astm", level="DEBUG") as cm:
            self.protocol.connection_lost(None)

        levels = [r.levelname for r in cm.records]
        messages = [r.getMessage() for r in cm.records]
        self.assertNotIn("WARNING", levels)
        self.assertTrue(
            any("without data" in m for m in messages),
            "expected an empty-session debug line, got %r" % messages,
        )

    def test_mid_session_disconnect_logs_at_warning(self):
        """A real session cut mid-message stays at WARNING so it
        remains visible in operational logs."""
        transport = self.get_mock_transport()
        self.protocol.connection_made(transport)
        # Simulate a partial session: ENQ received, frames buffered.
        self.protocol.in_transfer_state = True
        self.protocol.messages = [b"1H|"]

        with self.assertLogs("senaite.astm", level="DEBUG") as cm:
            self.protocol.connection_lost(None)

        self.assertIn("WARNING", [r.levelname for r in cm.records])

    def test_chunked_frame_assembled_across_recvs(self):
        """A complete ASTM frame split across two TCP segments
        must be reassembled into a single dispatched message, with
        the matching ACK going back to the client. Regression test
        for the production cobas c111 transmission where the R
        record arrived as two recvs and the continuation bytes
        were dropped as un-dispatchable."""
        transport = self.get_mock_transport()
        self.protocol.connection_made(transport)
        self.protocol.data_received(ENQ)

        # Hand-crafted R frame split mid-data. The checksum
        # matches the full frame body once reassembled.
        frame = (
            b"\x024R|1|^^^734|3.0|umol/L||N||F||$SYS$||"
            b"20260603110046\r\x03B2\r\n"
        )
        # Split in the middle of the date field, just like the log
        first, second = frame[:45], frame[45:]
        self.assertNotIn(b"\x03", first,
                         "split point must be before the terminator")

        self.protocol.data_received(first)
        # Nothing dispatched yet — buffer is short.
        self.assertEqual(len(self.protocol.messages), 0)

        self.protocol.data_received(second)
        # Now the frame is complete and stored as one message.
        self.assertEqual(len(self.protocol.messages), 1)
        # And the response to the (now complete) frame was an ACK.
        transport.write.assert_called_with(ACK)

    def test_two_full_frames_in_one_recv(self):
        """When a single TCP segment carries two complete frames
        back to back, both must be dispatched and ACKed."""
        transport = self.get_mock_transport()
        self.protocol.connection_made(transport)
        self.protocol.data_received(ENQ)

        # Two minimal valid frames concatenated.
        frame_a = b"\x021H|\\^&\r\x03E5\r\n"
        frame_b = b"\x022P|1\r\x033F\r\n"
        self.protocol.data_received(frame_a + frame_b)

        self.assertEqual(len(self.protocol.messages), 2)
        # Each frame produced an ACK; the last write is the second ACK.
        self.assertEqual(
            [c.args[0] for c in transport.write.call_args_list[-2:]],
            [ACK, ACK])
