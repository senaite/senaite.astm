# -*- coding: utf-8 -*-

import json
import pkgutil
import re
from collections import defaultdict

from senaite.astm import codec
from senaite.astm import instruments
from senaite.astm import records
from senaite.astm.constants import ENCODING
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
        self.mapping = self.get_mapping(messages)
        self.module = None

    def get_mapping(self, messages):
        """Returns the record mapping for the message
        """
        if not messages:
            return DEFAULT_MAPPING
        header = messages[0]

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

    def to_dict(self):
        """Convert the ASTM message to a dictionary

        Returns a dictionary where the key is the record type and the values is
        a list of value dictionaries:

            {
                'H': [{...}],
                ...
                'L': [{...}],
            }
        """

        # get the record mapping if provided
        mapping = self.get_mapping(self.messages)
        # Prepare some metadata
        metadata = {
            "astm": self.to_astm(),
            "lis2a": self.to_lis2a(),
        }
        # Append additional metadata if provided by the module
        metadata_func = getattr(self.module, "get_metadata", None)
        if callable(metadata_func):
            metadata.update(metadata_func(self))

        # Output dictionary
        out = defaultdict(list)
        out["metadata"] = metadata

        for message in self.messages:
            records = codec.decode(message)

            for record in records:
                rtype = record[0]
                if rtype not in mapping:
                    continue
                wrapper = mapping[rtype](*record)
                out[rtype].append(wrapper.to_dict())

        return out

    def to_json(self):
        data = json.dumps(self.to_dict())
        # Return the JSON encoded to bytes.
        return data.encode()
