# -*- coding: utf-8 -*-

import argparse
import importlib
import os
import pkgutil
import sys
from argparse import ArgumentError

from senaite.astm import logger
from senaite.astm import wrapper


def get_astm_wrappers():
    dirname = os.path.dirname(__file__)
    instr_dir = "instruments"
    pkg_dir = os.path.join(dirname, instr_dir)
    for (module_loader, name, ispkg) in pkgutil.iter_modules([pkg_dir]):
        importlib.import_module(
            'senaite.astm.instruments.' + name, __package__)
    return {
        cls.__name__: cls for cls in wrapper.ASTMWrapper.__subclasses__()
    }


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    wrappers = get_astm_wrappers()

    parser.add_argument(
        '-i',
        '--infile',
        type=str,
        help='Input file')

    parser.add_argument(
        '-o',
        '--outfile',
        type=str,
        help='Output file')

    parser.add_argument(
        '-p',
        '--parser',
        type=str,
        help='Available instrument parsers: {}'.format(
            ','.join(wrappers.keys())))

    args = parser.parse_args()

    infile = args.infile
    if not infile or not os.path.exists(infile):
        raise ArgumentError('Infile not found')

    # parse all ASTM messages from the file
    messages = []
    with open(infile, "rb") as fd:
        messages = fd.readlines()

    if not messages:
        logger.error('Error: File is empty')
        return sys.exit(1)

    parser = args.parser
    if parser not in wrappers.keys():
        logger.error('Error: Invalid parser selected')
        return sys.exit(1)

    wrapper = wrappers[parser](messages)
    records = wrapper.get_records()

    import pdb; pdb.set_trace()


if __name__ == '__main__':
    main()
