# -*- coding: utf-8 -*-

import argparse
import asyncio
import logging

from senaite.astm import logger
from senaite.astm.protocol import ASTMProtocol


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

    # Get the current event loop.
    loop = asyncio.get_event_loop()
    # Create a TCP server listening on port of the host address.
    coro = loop.create_server(ASTMProtocol, host=args.listen, port=args.port)
    # Run until the future (an instance of Future) has completed.
    server = loop.run_until_complete(coro)

    for socket in server.sockets:
        ip, port = socket.getsockname()
        logger.info('Starting server on {}:{}'.format(ip, port))
        logger.info('ASTM server ready to handle connections ...')

    # Run the event loop until stop() is called.
    loop.run_forever()


if __name__ == '__main__':
    main()
