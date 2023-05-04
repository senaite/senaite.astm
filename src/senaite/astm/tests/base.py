# -*- coding: utf-8 -*-

import asyncio
import os
from glob import glob
from unittest import IsolatedAsyncioTestCase

from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ


class ASTMTestBase(IsolatedAsyncioTestCase):
    """Base Test Class
    """
    HOST = "localhost"
    PORT = 7980

    @property
    def data_dir(self):
        """Returns the data directory
        """
        test_path = os.path.dirname(__file__)
        return os.path.join(test_path, "data")

    @property
    def instrument_files(self):
        """Returns all instrument files from the data directory
        """
        path = "{}/*.txt".format(self.data_dir)
        return glob(path)

    def get_instrument_file_path(self, filename):
        """Returns the instrument file path
        """
        return os.path.join(self.data_dir, filename)

    def read_file_lines(self, path, mode="rb"):
        """Read the lines of the file
        """
        with open(path, mode) as f:
            return f.readlines()

    async def communicate(self, data, **kw):
        """Simulate a full instrument communication
        """
        reader = kw.get("reader", None)
        writer = kw.get("writer", None)
        if not all([reader, writer]):
            reader, writer = await asyncio.open_connection(
                self.HOST, self.PORT)

        # Start with an ENQ
        writer.write(ENQ)
        await writer.drain()
        response = await reader.read(100)
        self.assertEqual(response, ACK)

        # Send instrument data
        for line in data:
            writer.write(line)
            await writer.drain()
            response = await reader.read(100)
            # We expect an ACK as response
            self.assertEqual(response, ACK)

        # close the connection
        writer.close()
        await writer.wait_closed()
