# -*- coding: utf-8 -*-

from collections import defaultdict

from senaite.astm import codec
from senaite.astm import instruments  # noqa: F401  (triggers registry)
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
        self.mapping = self.get_mapping(messages)

    def get_mapping(self, messages):
        """Return the record mapping for the message.

        Resolved against the instrument registry populated at import
        time by :func:`senaite.astm.core.instrument.register_instrument`.
        Falls back to :data:`DEFAULT_MAPPING` when no registered
        instrument claims the header (e.g. unknown device, empty
        message list).
        """
        if not messages:
            return DEFAULT_MAPPING
        instrument = find_instrument(messages[0])
        if instrument is None:
            return DEFAULT_MAPPING
        self.instrument = instrument
        return dict(instrument.record_map)

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
        metadata_extras = {
            "astm": self.to_astm(),
            "lis2a": self.to_lis2a(),
        }
        metadata_extras.update(self._collect_instrument_metadata())

        buckets = defaultdict(list)
        for message in self.messages:
            for record in codec.decode(message):
                rtype = record[0]
                if rtype not in self.mapping:
                    continue
                try:
                    wrapped = self.mapping[rtype](*record)
                except ValueError as exc:
                    raise ValueError(
                        "Could not wrap '%s' record" % rtype) from exc
                buckets[rtype].append(wrapped.to_dict())

        return Envelope(
            metadata=Metadata(**metadata_extras),
            **buckets,
        )

    def _collect_instrument_metadata(self):
        if self.instrument is None:
            return {}
        return dict(self.instrument.get_metadata(self) or {})

    def to_dict(self):
        """Return the envelope as a plain JSON-serialisable dict.

        Equivalent to :meth:`to_envelope` followed by
        ``model_dump(mode="json")``.
        """
        return self.to_envelope().model_dump(mode="json")

    def to_json(self):
        """Return the envelope as JSON-encoded bytes."""
        return self.to_envelope().model_dump_json().encode()
