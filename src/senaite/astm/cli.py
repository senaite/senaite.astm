# -*- coding: utf-8 -*-

import argparse
import asyncio
import contextlib
import logging
import os
import sys
from argparse import ArgumentError

from senaite.astm import logger
from senaite.astm.protocol import ASTMProtocol


async def consume(queue, callback=None):
    """ASTM Message consumer
    """
    while True:
        message = await queue.get()
        if callable(callback):
            callback(message)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        '-l',
        '--listen',
        type=str,
        default='0.0.0.0',
        help='Listen IP address')

    parser.add_argument(
        '-p',
        '--port',
        type=str,
        default='4010',
        help='Port to connect')

    parser.add_argument(
        '-o',
        '--output',
        type=str,
        default=os.getcwd(),
        help='Output directory to write ASTM files')

    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Verbose logging')

    args = parser.parse_args()

    # Set logging
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

    if not os.path.isdir(args.output):
        raise ArgumentError("Output path must be an existing directory")

    def dispatch_astm_message(message):
        """Dispatch astm message
        """
        print("DISPATCH ASTM MESSAGE!")

    # Get the current event loop.
    loop = asyncio.get_event_loop()

    # create a communication queue between the protocol and the server
    queue = asyncio.Queue()

    # Create a TCP server listening on port of the host address.
    server_coro = loop.create_server(
        lambda: ASTMProtocol(loop, queue), host=args.listen, port=args.port)

    # ASTM message consumer coroutine
    consumer = loop.create_task(
        consume(queue, callback=dispatch_astm_message))

    # Run until the future (an instance of Future) has completed.
    server = loop.run_until_complete(server_coro)

    for socket in server.sockets:
        ip, port = socket.getsockname()
        logger.info('Starting server on {}:{}'.format(ip, port))
        logger.info('ASTM server ready to handle connections ...')

    # Run the event loop until stop() is called.
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        all_tasks = asyncio.gather(
            *asyncio.all_tasks(loop), return_exceptions=True)
        all_tasks.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            loop.run_until_complete(all_tasks)
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        loop.close()
        logger.info("Server is now down...")


if __name__ == '__main__':
    main()
