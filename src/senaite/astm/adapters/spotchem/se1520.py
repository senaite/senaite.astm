# -*- coding: utf-8 -*-

import re
from datetime import datetime

from senaite.astm import adapter_registry
from senaite.astm import utils
from senaite.astm.constants import ENQ
from senaite.astm.constants import EOT
from senaite.astm.constants import NAK
from senaite.astm.interfaces import IDataHandler
from senaite.astm.utils import f
from senaite.astm.utils import u
from zope.interface import implementer

RX = (
    rb"\x02"                             # Start of the message
    rb"(\d{2}/\d{2}/\d{2})\s+"           # Date in YY/MM/DD format
    rb"(\d{2}:\d{2})\s+"                 # Time in HH:MM format
    rb"ID#\s*([A-Z0-9\-_]+)\s+"          # Sample ID prefixed by "ID#"
    rb"\[(.*?)\]\s+"                     # Sample type in square brackets
    rb"Na\s+([\d.]+)\s+(mmol/L)\s+"      # Na result
    rb"K\s+([\d.]+)\s+(mmol/L)\s+"       # K result
    rb"Cl\s+([\d.]+)\s+(mmol/L)"         # Cl result
    rb"\s*\x03"                          # End of the message
)


@implementer(IDataHandler)
class DataHandler:
    """Custom data handler for Spotchem SE-1520

    We receive from this instrument a non valid ASTM message that need to be
    handled differntly
    """
    def __init__(self, protocol, data):
        self.protocol = protocol
        self.data = data

    def can_handle(self):
        return re.match(RX, self.data) is not None

    def handle_data(self):
        """Create a valid ASTM message of the received data

        1. Create a static header record
        2. Create a results record with the given data
        3. Create a termination record

        """
        parts = re.match(RX, self.data)
        if not parts:
            return NAK

        # initialize the communication if we're not already in transfer state
        # Note: This is mainly a test fixture for the simulator
        if not self.protocol.in_transfer_state:
            self.protocol.on_enq(ENQ)

        date = parts.group(1).decode("utf-8")         # Date
        time = parts.group(2).decode("utf-8")         # Time
        sample_id = parts.group(3).decode("utf-8")    # Sample ID
        sample_type = parts.group(4).decode("utf-8")  # Sample type
        na_result = float(parts.group(5))             # Na result
        na_unit = parts.group(6).decode("utf-8")      # Na unit
        k_result = float(parts.group(7))              # K result
        k_unit = parts.group(8).decode("utf-8")       # K unit
        cl_result = float(parts.group(9))             # Cl result
        cl_unit = parts.group(10).decode("utf-8")     # Cl unit

        # convert date and time to a timestamp
        dt = datetime.strptime(f"{date} {time}", "%y/%m/%d %H:%M")
        timestamp = dt.strftime("%Y%m%d%H%M%S")

        frames = [
            f("1H|\\^&|||SE-1520^Spotchem^1.0.0|||||||||{ts}{CR}{ETX}",
              ts=timestamp),
            f("2O|1|{sid}||{stype}|||{ts}||||||||||||||||||{CR}{ETX}",
              sid=sample_id, stype=sample_type, ts=timestamp),
            f("3R|1|Na|{result}|{unit}||||||||{ts}|{CR}{ETX}",
              result=na_result, unit=na_unit, ts=timestamp),
            f("4R|2|K|{result}|{unit}||||||||{ts}|{CR}{ETX}",
              result=k_result, unit=k_unit, ts=timestamp),
            f("5R|3|Cl|{result}|{unit}||||||||{ts}|{CR}{ETX}",
              result=cl_result, unit=cl_unit, ts=timestamp),
            f("6L|1|N{CR}{ETX}"),
        ]
        messages = []
        for frame in frames:
            cs = utils.make_checksum(frame)
            messages.append(
                f("{STX}{frame}{cs}{CRLF}", frame=u(frame), cs=u(cs)))

        # fill in the full message
        self.protocol.messages = messages

        # end the communicaiton
        self.protocol.on_eot(EOT)


# register the adapter
adapter_registry.registerAdapter(
    DataHandler,
    required=(object, object),
    provided=IDataHandler,
)
