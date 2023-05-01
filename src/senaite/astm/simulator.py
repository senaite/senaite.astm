# -*- coding: utf-8 -*-

import argparse
import asyncio
import logging
import random

from senaite.astm import logger
from senaite.astm.constants import CRLF
from senaite.astm.constants import ENQ
from senaite.astm.constants import EOT
from senaite.astm.constants import ACK


def main():
    # Argument parser
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # Argument groups
    astm_group = parser.add_argument_group('ASTM SERVER')

    astm_group.add_argument(
        '-a',
        '--address',
        type=str,
        default='127.0.0.1',
        help='ASTM Server IP')

    astm_group.add_argument(
        '-p',
        '--port',
        type=str,
        default='4010',
        help='ASTM Server Port')

    astm_group.add_argument(
        '-i',
        '--infile',
        type=argparse.FileType('rb'),
        nargs='+',
        help='ASTM file(s) to send')

    astm_group.add_argument(
        '-d',
        '--delay',
        type=float,
        default=0.1,
        help='Delay in seconds between two frames.')

    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Verbose logging')

    # Parse Arguments
    args = parser.parse_args()

    # Set logging
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

    # Get the current event loop.
    loop = asyncio.get_event_loop()

    messages = []
    for f in args.infile:
        messages.append(f.readlines())

    coro = send_messages(messages, args.address, args.port, delay=args.delay)

    try:
        loop.run_until_complete(coro)
    except KeyboardInterrupt:
        logger.info('Shutting down...')
        coro.cancel()
    finally:
        loop.close()
        logger.info('Done')


async def send_messages(messages, address, port, **kw):
    """Send all given messages through a single connection
    """
    rport = random.randint(55000, 60000)
    local_addr = ("127.0.0.1", rport, )
    reader, writer = await asyncio.open_connection(
        address, port, local_addr=local_addr)
    logger.info("Connecting from {!r}".format(local_addr))
    for message in messages:
        await send_message(message, reader, writer, **kw)
    writer.close()
    await writer.wait_closed()


async def send_message(message, reader, writer, **kw):
    """Send message to ASTM server
    """
    # get the delay
    delay = kw.get('delay', 0.0)

    # Start each new message with an ENQ
    logger.info('-> Write ENQ')
    writer.write(ENQ)
    await writer.drain()
    response = await reader.read(100)
    logger.info('<- Got response: {!r}'.format(response))

    for line in message:
        # Remove trailing \r\n
        line = line.strip(CRLF)
        logger.info('-> Sending data: {!r}'.format(line))
        await asyncio.sleep(delay)
        writer.write(line)
        await writer.drain()
        response = await reader.read(100)
        logger.info('<- Got response: {!r}'.format(response))
        if response != ACK:
            logger.error('Expected ACK, got {!r}'.format(response))
            break

    writer.write(EOT)
    logger.info('-> Write EOT')
    await writer.drain()
    response = await reader.read(100)
    logger.info('<- Got response: {!r}'.format(response))


if __name__ == '__main__':
    main()
