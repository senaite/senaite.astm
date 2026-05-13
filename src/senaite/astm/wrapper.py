# -*- coding: utf-8 -*-

import pkgutil
import re
from collections import defaultdict

from senaite.astm import codec
from senaite.astm import instruments
from senaite.astm import records
from senaite.astm.constants import ENCODING
from senaite.astm.core.envelope import Envelope
from senaite.astm.core.envelope import Metadata
from senaite.astm.core.instrument import find_instrument
from senaite.astm.utils import split_message

DEFAULT_MAPPING = {
    "H": records.HeaderRecord,
    "P": records.PatientRecord,
    "O": records.OrderRecord,
    "R": records.ResultRecord,
    "C": records.CommentRecord,
    "Q": records.RequestInformationRecord,
    "M": records.ManufacturerInfoRecord,
    "L": records.TerminatorRecord,
}


class Wrapper(object):
    """Message wrapper
    """
    def __init__(self, messages):
        self.messages = messages
        self.instrument = None
        self.module = None
        self.mapping = self.get_mapping(messages)

    def get_mapping(self, messages):
        """Returns the record mapping for the message.

        Resolution order:

        1. The instrument registry populated by
           :func:`senaite.astm.core.instrument.register_instrument`.
        2. Legacy ``pkgutil``-based discovery of
           :mod:`senaite.astm.instruments` modules (kept until
           every instrument is migrated; will be removed in PR-E2).
        3. The :data:`DEFAULT_MAPPING` fallback.
        """
        if not messages:
            return DEFAULT_MAPPING
        header = messages[0]

        instrument = find_instrument(header)
        if instrument is not None:
            self.instrument = instrument
            return dict(instrument.record_map)

        return self._legacy_mapping(header)

    def _legacy_mapping(self, header):
        for importer, modname, ispkg in pkgutil.iter_modules(
                instruments.__path__, instruments.__name__ + "."):
            module = __import__(modname, fromlist="dummy")
            # get the regular expression to match the header message
            regex = getattr(module, "HEADER_RX", None)
            if regex and re.match(regex, header.decode()):
                mapping = getattr(module, "get_mapping", None)
                if callable(mapping):
                    return mapping()
                # remember the matching module
                self.module = module

        return DEFAULT_MAPPING

    def to_lis2a(self, encoding=ENCODING):
        out = b""
        for message in self.messages:
            seq, msg, cs = split_message(message)
            out += msg
        return out.decode(encoding)

    def to_astm(self, encoding=ENCODING):
        out = b"\n".join(self.messages)
        return out.decode(encoding)

    def to_envelope(self):
        """Parse the ASTM messages into a typed :class:`Envelope`.

        See :mod:`senaite.astm.core.envelope` for the schema and
        the contract guarantees.
        """
        mapping = self.get_mapping(self.messages)

        metadata_extras = {
            "astm": self.to_astm(),
            "lis2a": self.to_lis2a(),
        }
        metadata_extras.update(self._collect_instrument_metadata())

        buckets = defaultdict(list)
        for message in self.messages:
            for record in codec.decode(message):
                rtype = record[0]
                if rtype not in mapping:
                    continue
                try:
                    wrapped = mapping[rtype](*record)
                except ValueError as exc:
                    raise ValueError("Could not wrap '%s' record! (%s)"
                                     % (rtype, str(exc)))
                buckets[rtype].append(wrapped.to_dict())

        return Envelope(
            metadata=Metadata(**metadata_extras),
            **buckets,
        )

    def _collect_instrument_metadata(self):
        """Merge instrument-specific metadata from whichever
        mechanism resolved the mapping.
        """
        if self.instrument is not None:
            extras = self.instrument.get_metadata(self)
            return dict(extras or {})
        get_metadata = getattr(self.module, "get_metadata", None)
        if callable(get_metadata):
            return dict(get_metadata(self) or {})
        return {}

    def to_dict(self):
        """Return the envelope as a plain JSON-serialisable dict.

        Equivalent to :meth:`to_envelope` followed by
        ``model_dump(mode="json")``.
        """
        return self.to_envelope().model_dump(mode="json")

    def to_json(self):
        """Return the envelope as JSON-encoded bytes."""
        return self.to_envelope().model_dump_json().encode()
