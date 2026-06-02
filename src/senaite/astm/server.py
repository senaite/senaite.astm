# -*- coding: utf-8 -*-

import argparse
import asyncio
import contextlib
import logging
import os
import sys

from senaite.astm import lims
from senaite.astm import logger
from senaite.astm.lims import post_to_senaite
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.utils import write_message

LOGFILE = "senaite-astm-server.log"


async def consume(queue, callback=None):
    """ASTM Message consumer coroutine function
    """
    while True:
        message = await queue.get()
        if callable(callback):
            callback(message)


async def connect_forever(loop, host, port, protocol_factory, reconnect_delay):
    """Client (connect) mode main coroutine.

    Actively opens an outbound connection to an instrument or serial-to-LAN
    gateway at ``host:port`` (useful when the device is configured as a passive
    TCP server and expects the LIS to initiate the connection). Keeps the
    connection open and transparently reconnects when it drops.
    """
    while True:
        # Future resolved by the protocol when the connection is lost
        on_connection_lost = loop.create_future()
        try:
            logger.info(
                'Connecting to instrument at {}:{} ...'.format(host, port))
            await loop.create_connection(
                lambda: protocol_factory(on_connection_lost),
                host=host, port=port)
        except OSError as exc:
            logger.warning(
                'Connection to {}:{} failed: {}. Retrying in {}s ...'.format(
                    host, port, exc, reconnect_delay))
            await asyncio.sleep(reconnect_delay)
            continue

        logger.info('Connected to instrument at {}:{}'.format(host, port))
        logger.info('ASTM client ready to receive messages ...')
        # Block until the connection drops, then reconnect
        await on_connection_lost
        logger.warning(
            'Connection to {}:{} lost. Reconnecting in {}s ...'.format(
                host, port, reconnect_delay))
        await asyncio.sleep(reconnect_delay)


def main():
    # Argument parser
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # Argument groups
    astm_group = parser.add_argument_group('ASTM SERVER')
    lims_group = parser.add_argument_group('SENAITE LIMS')

    astm_group.add_argument(
        '-l',
        '--listen',
        type=str,
        default='0.0.0.0',
        help='Listen IP address')

    astm_group.add_argument(
        '-p',
        '--port',
        type=str,
        default='4010',
        help='Port to connect')

    astm_group.add_argument(
        '-o',
        '--output',
        type=str,
        help='Output directory to write full messages')

    astm_group.add_argument(
        '--connect',
        type=str,
        default=None,
        metavar='HOST:PORT',
        help='Client mode: actively connect OUT to an instrument or '
             'serial-to-LAN gateway at HOST:PORT instead of listening. Use '
             'this when the device is a passive TCP server and expects the '
             'LIS to initiate the connection. Mutually exclusive with '
             '--listen/--port.')

    astm_group.add_argument(
        '--reconnect-delay',
        type=int,
        default=5,
        help='Seconds to wait before (re)connecting in --connect mode')

    lims_group.add_argument(
        '-u',
        '--url',
        type=str,
        help='SENAITE URL address including username and password in the '
             'format: http(s)://<user>:<password>@<senaite_url>')

    lims_group.add_argument(
        '-c',
        '--consumer',
        type=str,
        default='senaite.core.lis2a.import',
        help='SENAITE push consumer interface')

    lims_group.add_argument(
        '-m',
        '--message-format',
        type=str,
        default='json',
        help='Message format to send to SENAITE. '
             'Allowed formats: "astm", "lis2a", "json".')

    lims_group.add_argument(
        '-r',
        '--retries',
        type=int,
        default=3,
        help='Number of attempts of reconnection when SENAITE '
             'instance is not reachable. Only has effect when '
             'argument --url is set')

    lims_group.add_argument(
        '-d',
        '--delay',
        type=int,
        default=5,
        help='Time delay in seconds between retries when '
             'SENAITE instance is not reachable. Only has '
             'effect when argument --url is set')

    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Verbose logging')

    parser.add_argument(
        '--logfile',
        default=LOGFILE,
        help='Path to store log files')

    # Parse Arguments
    args = parser.parse_args()

    if args.logfile:
        handler = logging.handlers.RotatingFileHandler(
            args.logfile, maxBytes=5, backupCount=0)
        # Format each log message like this
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)-8s %(message)s')
        # Attach the formatter to the handler
        handler.setFormatter(formatter)
        # Attach the handler to the logger
        logger.addHandler(handler)

    # Get the current event loop.
    loop = asyncio.get_event_loop()

    # Set logging
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

    # Validate output path
    output = args.output
    if output and not os.path.isdir(args.output):
        logger.error('Output path must be an existing directory')
        return sys.exit(-1)

    # Validate SENAITE URL
    url = args.url
    if url:
        session = lims.Session(url)
        logger.info('Checking connection to SENAITE ...')
        if not session.auth():
            return sys.exit(-1)

    def dispatch_astm_message(message):
        """Dispatch astm message
        """
        logger.debug('Dispatching ASTM Message')
        if output:
            path = os.path.abspath(output)
            loop.create_task(
                asyncio.to_thread(
                    write_message, message, path))
        if url:
            session = lims.Session(url)
            session_args = {
                'delay': args.delay,
                'retries': args.retries,
                'consumer': args.consumer,
            }
            loop.create_task(
                asyncio.to_thread(
                    post_to_senaite, message, session, **session_args))

    # Create a ASTM message consumer task to be scheduled concurrently.
    queue = asyncio.Queue()
    loop.create_task(consume(queue, callback=dispatch_astm_message))

    if args.connect:
        # CLIENT (connect) mode: actively connect out to the instrument/gateway
        host, sep, port = args.connect.partition(':')
        if not sep or not host or not port:
            logger.error('--connect requires the format HOST:PORT')
            return sys.exit(-1)

        def protocol_factory(on_connection_lost):
            return ASTMProtocol(
                queue=queue,
                message_format=args.message_format,
                on_connection_lost=on_connection_lost)

        try:
            loop.run_until_complete(
                connect_forever(loop, host, int(port), protocol_factory,
                                args.reconnect_delay))
        except KeyboardInterrupt:
            logger.info('Shutting down client...')
        finally:
            loop.close()
            logger.info('Client is now down...')
        return

    # SERVER (listen) mode
    # Create a TCP server coroutine listening on port of the host address.
    # IMPORTANT: We create a new Protocol for every connection!
    server_coro = loop.create_server(
        lambda: ASTMProtocol(queue=queue, message_format=args.message_format),
        host=args.listen, port=args.port)

    # Run until the future (an instance of Future) has completed.
    server = loop.run_until_complete(server_coro)

    for socket in server.sockets:
        ip, port = socket.getsockname()
        logger.info('Starting server on {}:{}'.format(ip, port))
        logger.info('ASTM server ready to handle connections ...')

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info('Shutting down server...')
        all_tasks = asyncio.gather(
            *asyncio.all_tasks(loop), return_exceptions=True)
        all_tasks.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            loop.run_until_complete(all_tasks)
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        loop.close()
        logger.info('Server is now down...')


if __name__ == '__main__':
    main()
