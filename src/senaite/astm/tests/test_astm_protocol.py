
# -*- coding: utf-8 -*-

import os
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock
from unittest.mock import Mock

from senaite.astm.constants import ACK
from senaite.astm.constants import CRLF
from senaite.astm.constants import ENQ
from senaite.astm.constants import EOT
from senaite.astm.constants import NAK
from senaite.astm.protocol import ASTMProtocol


class ASTMProtocolTest(IsolatedAsyncioTestCase):
    """Test ASTM Communication Protocol
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

    def get_instrument_file_path(self, filename="yumizen_h500.txt"):
        """Returns the instrument file path
        """
        test_path = os.path.dirname(__file__)
        return os.path.join(test_path, "data", filename)

    def read_file(self, path, mode="rb"):
        """Read the data of the file
        """
        with open(path, mode) as f:
            return f.read()

    def read_file_lines(self, path, mode="rb"):
        """Read the lines of the file
        """
        with open(path, mode) as f:
            return f.readlines()

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
        path = self.get_instrument_file_path()
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
