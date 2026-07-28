# -*- coding: utf-8 -*-

import re
from datetime import datetime

from senaite.astm import records
from senaite.astm import utils
from senaite.astm.constants import ENQ
from senaite.astm.constants import EOT
from senaite.astm.constants import NAK
from senaite.astm.core.instrument import Instrument
from senaite.astm.core.instrument import register_instrument
from senaite.astm.fields import ComponentField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component
from senaite.astm.utils import f as fmt
from senaite.astm.utils import u

VERSION = "1.0.0"
# Supports SE1520
HEADER_RX = re.compile(rb".*SE-1520\^")

# Raw, non-ASTM wire format emitted by the SE-1520.
RAW_DATA_RX = re.compile(
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


class HeaderRecord(records.HeaderRecord):
    """Message Header Record (H)
    """
    sender = ComponentField(
        Component.build(
            TextField(name="name"),
            TextField(name="manufacturer", default="Spotchem"),
            TextField(name="version"),
        ))
    timestamp = DateTimeField()


class OrderRecord(records.OrderRecord):

    sample_id = TextField()
    test = TextField()
    sampled_at = DateTimeField()


class ResultRecord(records.ResultRecord):
    """Record to transmit analytical data.

    Example:
    2R|1|Na|{result}|{unit}|||||||||
    """

    # 10.1.3: Universal Test ID
    #         Example: ^^^103^D
    test = TextField()

    # 10.1.4: Data or Measurement Value
    value = TextField()

    # 10.1.5: Units
    #         Example: mg/dL
    units = TextField()

    # 10.1.13: Date time test completed
    completed_at = DateTimeField()


class TerminatorRecord(records.TerminatorRecord):
    """Message Termination Record (L)
    """


@register_instrument
class SpotchemEL(Instrument):
    name = "spotchem_el"
    header_regex = HEADER_RX
    raw_data_regex = RAW_DATA_RX
    record_map = {
        "H": HeaderRecord,
        "O": OrderRecord,
        "R": ResultRecord,
        "L": TerminatorRecord,
    }

    def get_metadata(self, wrapper):
        return {"version": VERSION,
                "header_rx": HEADER_RX.pattern.decode()}

    def handle_raw_data(self, protocol, data):
        """Synthesise a complete ASTM session from a single non-ASTM
        packet emitted by the Spotchem SE-1520.

        Drives ``protocol`` directly: ENQ, queue the synthetic ASTM
        frames, EOT.
        """
        parts = re.match(RAW_DATA_RX, data)
        if not parts:
            return NAK
        if not protocol.in_transfer_state:
            protocol.on_enq(ENQ)

        date = parts.group(1).decode("utf-8")
        time = parts.group(2).decode("utf-8")
        sample_id = parts.group(3).decode("utf-8")
        sample_type = parts.group(4).decode("utf-8")
        na_result = float(parts.group(5))
        na_unit = parts.group(6).decode("utf-8")
        k_result = float(parts.group(7))
        k_unit = parts.group(8).decode("utf-8")
        cl_result = float(parts.group(9))
        cl_unit = parts.group(10).decode("utf-8")

        dt = datetime.strptime("%s %s" % (date, time), "%y/%m/%d %H:%M")
        timestamp = dt.strftime("%Y%m%d%H%M%S")

        frames = [
            fmt(
                "1H|\\^&|||SE-1520^Spotchem^1.0.0|||||||||{ts}{CR}{ETX}",
                ts=timestamp),
            fmt(
                "2O|1|{sid}||{stype}|||{ts}||||||||||||||||||{CR}{ETX}",
                sid=sample_id, stype=sample_type, ts=timestamp),
            fmt(
                "3R|1|Na|{result}|{unit}||||||||{ts}|{CR}{ETX}",
                result=na_result, unit=na_unit, ts=timestamp),
            fmt(
                "4R|2|K|{result}|{unit}||||||||{ts}|{CR}{ETX}",
                result=k_result, unit=k_unit, ts=timestamp),
            fmt(
                "5R|3|Cl|{result}|{unit}||||||||{ts}|{CR}{ETX}",
                result=cl_result, unit=cl_unit, ts=timestamp),
            fmt("6L|1|N{CR}{ETX}"),
        ]
        messages = []
        for frame in frames:
            cs = utils.make_checksum(frame)
            messages.append(
                fmt("{STX}{frame}{cs}{CRLF}", frame=u(frame), cs=u(cs)))

        protocol.messages = messages
        protocol.on_eot(EOT)
        return None


INSTRUMENT = SpotchemEL()
