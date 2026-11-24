# -*- coding: utf-8 -*-
"""Client (connect) mode tests.

In client mode senaite.astm connects out to an instrument or
serial-to-LAN gateway that behaves as a passive TCP server (e.g. a
Lantronix configured with "Accept Incoming = Yes" / "Active Connect =
None"). This is the inverse of the server tests: here the *instrument*
listens, and senaite.astm initiates the connection and then plays the
receiver side of the ASTM handshake.
"""

import argparse
import asyncio

from senaite.astm import logger
from senaite.astm.cli import astm_server
from senaite.astm.cli.astm_server import connect_forever
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.constants import EOT
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.transports.astm.protocol import ASTMProtocol
from senaite.astm.wrapper import Wrapper

FIXTURE = "cobas_c111.txt"


class ASTMClientTest(ASTMTestBase):
    """senaite.astm as the TCP client connecting to a passive instrument
    """

    PORT = 7984

    async def asyncSetUp(self):
        logger.info("\n------------> asyncSetUp client")
        self.sessions = asyncio.Queue()
        path = self.get_instrument_file_path(FIXTURE)
        self.data = self.read_file_lines(path)
        self.connections = 0
        # The fake passive instrument: it listens, and we connect to it
        self.instrument = await asyncio.start_server(
            self.instrument_handler, host=self.HOST, port=self.PORT)

    async def asyncTearDown(self):
        self.instrument.close()
        await self.instrument.wait_closed()

    async def instrument_handler(self, reader, writer):
        """Plays the instrument (sender) side: ENQ -> frames -> EOT
        """
        self.connections += 1
        writer.write(ENQ)
        await writer.drain()
        if await reader.readexactly(1) != ACK:
            writer.close()
            return
        for line in self.data:
            writer.write(line)
            await writer.drain()
            # ACK per frame
            await reader.readexactly(1)
        writer.write(EOT)
        await writer.drain()
        writer.close()

    def frame_callback(self, client, frames):
        self.sessions.put_nowait(frames)

    def protocol_factory(self, lost):
        return ASTMProtocol(
            frame_callback=self.frame_callback, on_connection_lost=lost)

    def start_client(self):
        return asyncio.get_running_loop().create_task(
            connect_forever(self.HOST, self.PORT, self.protocol_factory,
                            reconnect_delay=1))

    async def stop_client(self, task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def test_client_collects_session(self):
        """The client connects out, and the session is handed over as
        the same frames the server mode produces
        """
        task = self.start_client()
        try:
            frames = await asyncio.wait_for(self.sessions.get(), timeout=5)
        finally:
            await self.stop_client(task)
        envelope = Wrapper(frames).to_dict()
        self.assertEqual(len(envelope["H"]), 1)
        self.assertIn("astm", envelope["metadata"])

    async def test_client_reconnects_after_drop(self):
        """When the instrument closes the connection, the client
        connects again and collects the next session
        """
        task = self.start_client()
        try:
            first = await asyncio.wait_for(self.sessions.get(), timeout=5)
            second = await asyncio.wait_for(self.sessions.get(), timeout=8)
        finally:
            await self.stop_client(task)
        self.assertEqual(first, second)
        self.assertGreaterEqual(self.connections, 2)

    async def test_client_retries_when_refused(self):
        """The client keeps trying while the instrument is not
        listening, and connects once it is
        """
        self.instrument.close()
        await self.instrument.wait_closed()
        task = self.start_client()
        try:
            # first attempt is refused
            await asyncio.sleep(0.5)
            self.assertTrue(self.sessions.empty())
            self.instrument = await asyncio.start_server(
                self.instrument_handler, host=self.HOST, port=self.PORT)
            frames = await asyncio.wait_for(self.sessions.get(), timeout=5)
        finally:
            await self.stop_client(task)
        self.assertTrue(frames)

    async def test_amain_stops_in_connect_mode(self):
        """`amain` runs the client loop with --connect, and shuts down
        cleanly when asked to
        """
        args = astm_server.build_arg_parser().parse_args(
            ["--connect", "{}:{}".format(self.HOST, self.PORT),
             "--reconnect-delay", "1"])
        args.session = None
        stop_event = asyncio.Event()
        main = asyncio.get_running_loop().create_task(
            astm_server.amain(args, stop_event=stop_event))
        # wait for the instrument to see the connection
        for _ in range(50):
            if self.connections:
                break
            await asyncio.sleep(0.1)
        stop_event.set()
        await asyncio.wait_for(main, timeout=5)
        self.assertGreaterEqual(self.connections, 1)


class HostPortTest(ASTMTestBase):

    def test_host_port(self):
        self.assertEqual(astm_server.host_port("10.0.0.5:4010"),
                         ("10.0.0.5", 4010))

    def test_invalid_host_port(self):
        for value in ("10.0.0.5", ":4010", "10.0.0.5:", "host:port"):
            with self.assertRaises(argparse.ArgumentTypeError):
                astm_server.host_port(value)
