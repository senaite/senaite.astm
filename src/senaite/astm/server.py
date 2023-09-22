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
        default='lis2a',
        help='Message format to send to SENAITE.'
             'Allowed formats "astm", "lis2a", "json".')

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
