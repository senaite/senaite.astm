# -*- coding: utf-8 -*-

import argparse
import logging

from senaite.astm import lims
from senaite.astm import logger
from senaite.astm.lims import post_to_senaite


def main():
    # Argument parser
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    astm_group = parser.add_argument_group('ASTM')
    lims_group = parser.add_argument_group('SENAITE LIMS')

    astm_group.add_argument(
        '-i',
        '--infile',
        type=argparse.FileType('rb'),
        nargs='+',
        help='ASTM file(s) to send to SENAITE')

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
        default='senaite.lis2a.import',
        help='SENAITE push consumer interface')

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

    # Parse Arguments
    args = parser.parse_args()

    # Set logging
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

    messages = []
    for f in args.infile:
        messages.append(f.read())

    if messages:
        url = args.url
        if url:
            session = lims.Session(url)
            session_args = {
                'delay': args.delay,
                'retries': args.retries,
                'consumer': args.consumer,
            }
            post_to_senaite(messages, session, **session_args)


if __name__ == '__main__':
    main()
