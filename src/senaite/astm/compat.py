# -*- coding: utf-8 -*-
#
# Credits to Alexander Shorin:
# https://github.com/kxepal/python-astm/blob/master/astm/compat.py

import sys

version = ".".join(map(str, sys.version_info[:2]))

if version >= "3.0":
    basestring = (str, bytes)
    unicode = str
    bytes = bytes
    long = int

    def buffer(obj, start=None, stop=None):
        memoryview(obj)
        if start is None:
            start = 0
        if stop is None:
            stop = len(obj)
        x = obj[start:stop]
        return x
else:
    basestring = basestring
    unicode = unicode
    b = bytes = str
    long = long
    buffer = buffer

b = lambda s: isinstance(s, unicode) and s.encode("latin1") or s  # noqa: E731
u = lambda s: isinstance(s, bytes) and s.decode("utf-8") or s  # noqa: E731


def make_string(value):
    if isinstance(value, unicode):
        return value
    elif isinstance(value, bytes):
        return unicode(value, "utf-8")
    else:
        return unicode(value)
