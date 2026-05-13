# -*- coding: utf-8 -*-
"""Instrument registry.

A single mechanism for describing a supported analyzer:

- a human-readable :attr:`name` (also used as the registry key),
- a :attr:`header_regex` matched against the first ASTM message to
  identify the device,
- a :attr:`record_map` mapping record type characters (H, P, O, R, ...)
  to the typed record class used to parse them,
- optional :meth:`preparse` and :meth:`get_metadata` hooks.

Instruments register themselves at import time via the
:func:`register_instrument` decorator. :func:`find_instrument`
resolves an instrument from a raw header line; overlapping regexes
raise :class:`AmbiguousInstrumentError` rather than silently picking
one match.

PR-E1 introduces the mechanism without migrating any instrument.
PR-E2 will move every instrument to this registry and remove the
legacy ``pkgutil``-based discovery in :mod:`senaite.astm.wrapper`.
"""

import re

from senaite.astm import logger

_REGISTRY = {}


class AmbiguousInstrumentError(LookupError):
    """Raised when more than one registered instrument matches the
    same header. The caller must rename or tighten one of the
    regexes; falling back to "first match wins" hides bugs.
    """


class Instrument(object):
    """Base class for registered instruments.

    Subclasses set :attr:`name`, :attr:`header_regex`, and
    :attr:`record_map`. Override :meth:`preparse` or
    :meth:`get_metadata` when needed.
    """

    name = None
    header_regex = None
    record_map = None
    #: Optional bytes regex used by :func:`find_raw_data_handler`
    #: to dispatch non-ASTM transport packets to this instrument
    #: before the standard ENQ/STX/EOT state machine sees them.
    raw_data_regex = None

    def can_handle(self, raw_header):
        """Return True if this instrument owns *raw_header*.

        Default implementation matches :attr:`header_regex` against
        the bytes of the first ASTM frame.
        """
        if self.header_regex is None:
            return False
        return re.match(self.header_regex, raw_header) is not None

    def can_handle_raw(self, data):
        """Return True if this instrument owns the raw, non-ASTM
        packet in *data*. Used by transports that wrap a custom
        wire format (mini_vidas, spotchem se1520) and need a shot
        at the bytes before the protocol's STX/ENQ dispatch.
        """
        if self.raw_data_regex is None:
            return False
        return re.match(self.raw_data_regex, data) is not None

    def handle_raw_data(self, protocol, data):
        """Hook for non-compliant transports.

        Default: ``None`` (no rewrite). Instruments whose wire
        format is not valid ASTM override this to synthesise a
        full ASTM session — typically by populating
        ``protocol.messages`` and driving ``protocol.on_enq`` /
        ``protocol.on_eot`` directly.

        :returns: bytes to write back to the device, or ``None``
            when the handler has already taken full responsibility.
        """
        return None

    def get_metadata(self, wrapper):
        """Optional per-instrument metadata merged into the envelope.

        Default returns an empty dict.
        """
        return {}


def register_instrument(cls):
    """Decorator: register an :class:`Instrument` subclass.

    Validates the class shape and instantiates it once. Re-registering
    the same name replaces the previous entry (with a debug log) so
    test fixtures can swap implementations.
    """
    if not isinstance(cls, type) or not issubclass(cls, Instrument):
        raise TypeError(
            "register_instrument expects an Instrument subclass, "
            "got %r" % (cls,))
    if not cls.name:
        raise ValueError(
            "Instrument %r must define a non-empty 'name'" % cls)
    if cls.header_regex is None:
        raise ValueError(
            "Instrument %r must define 'header_regex'" % cls)
    if not cls.record_map:
        raise ValueError(
            "Instrument %r must define a non-empty 'record_map'" % cls)
    if cls.name in _REGISTRY:
        logger.debug(
            "Replacing already-registered instrument %r", cls.name)
    _REGISTRY[cls.name] = cls()
    return cls


def unregister_instrument(name):
    """Remove *name* from the registry. No-op when absent.

    Intended for tests; production code should not call this.
    """
    _REGISTRY.pop(name, None)


def registered_instruments():
    """Return a tuple of registered :class:`Instrument` instances.

    Order is the order of registration.
    """
    return tuple(_REGISTRY.values())


def find_raw_data_handler(data):
    """Resolve a registered instrument that wants to handle the raw,
    non-ASTM *data* packet directly. Mirrors :func:`find_instrument`
    but consults :meth:`Instrument.can_handle_raw`.

    :raises AmbiguousInstrumentError: when more than one match.
    """
    matches = [inst for inst in _REGISTRY.values()
               if inst.can_handle_raw(data)]
    if len(matches) > 1:
        names = ", ".join(repr(m.name) for m in matches)
        raise AmbiguousInstrumentError(
            "Raw data matched multiple instruments: %s" % names)
    if matches:
        return matches[0]
    return None


def find_instrument(raw_header):
    """Resolve the instrument that owns *raw_header*.

    :param raw_header: bytes of the first ASTM message.
    :returns: the matching :class:`Instrument` instance, or ``None``
        when no instrument claims the header.
    :raises AmbiguousInstrumentError: when more than one registered
        instrument matches.
    """
    matches = [inst for inst in _REGISTRY.values()
               if inst.can_handle(raw_header)]
    if len(matches) > 1:
        names = ", ".join(repr(m.name) for m in matches)
        raise AmbiguousInstrumentError(
            "Header matched multiple instruments: %s" % names)
    if matches:
        return matches[0]
    return None


__all__ = (
    "AmbiguousInstrumentError",
    "Instrument",
    "find_instrument",
    "find_raw_data_handler",
    "register_instrument",
    "registered_instruments",
    "unregister_instrument",
)
