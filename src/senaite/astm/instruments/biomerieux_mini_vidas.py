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
from senaite.astm.fields import ComponentField, DateField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component
from senaite.astm.utils import f as fmt
from senaite.astm.utils import u

VERSION = "1.0.0"
# Supports Biomérieux miniVidas
HEADER_RX = re.compile(rb".*miniVidas\^")

# Raw, non-ASTM wire format emitted by the miniVidas.
RAW_DATA_RX = re.compile(
    rb"\x02"                                     # Start of the message
    rb"(?:\x1emt(?P<mt>[^|]*))?"                 # Message Type
    rb"(?:\|\x1epi(?P<pi>[^|]*))?"               # Patient Identifier
    rb"(?:\|\x1epn(?P<pn>[^|]*))?"               # Patient Name
    rb"(?:\|\x1epb(?P<pb>[^|]*))?"               # Patient Birthdate
    rb"(?:\|\x1eps(?P<ps>[^|]*))?"               # Patient Sex
    rb"(?:\|\x1eso(?P<so>[^|]*))?"               # Sample Origin
    rb"(?:\|\x1esi(?P<si>[^|]*))?"               # Specimen separator
    rb"(?:\|\x1eci(?P<ci>[^|]*))?"               # Sample Identifier
    rb"(?:\|\x1ert(?P<rt>[^|]*))?"               # Short assay name
    rb"(?:\|\x1ern(?P<rn>[^|]*))?"               # Long assay name
    rb"(?:\|\x1ett(?P<tt>[^|]*))?"               # Test completion time
    rb"(?:\|\x1etd(?P<td>[^|]*))?"               # Test completion date
    rb"(?:\|\x1eql(?P<ql>[^|]*))?"               # Qualitative Result
    rb"(?:\|\x1eqn(?P<qn>[^|]*))?"               # Quantitative Result
    rb"(?:\|\x1ey3(?P<y3>[^|]*))?"               # Unit associated with qn
    rb"(?:\|\x1eqd(?P<qd>[^|]*))?"               # Dilution
    rb"(?:\|\x1enc(?P<nc>[^|]*))?"               # Vidas flags
    rb"(?:\|\x1eid(?P<id>[^|]*))?"               # Instrument ID
    rb"(?:\|\x1esn(?P<sn>[^|]*))?"               # Serial Number
    rb"(?:\|\x1em4(?P<m4>[^|]*))?"               # Technologist
    rb"(?:\|\x1d(?P<checksum>[a-fA-F0-9]{2}))$"  # Checksum
)


class HeaderRecord(records.HeaderRecord):
    """Message Header Record (H)
    """
    sender = ComponentField(
        Component.build(
            TextField(name="name"),
            TextField(name="manufacturer", default="Biomerieux"),
            TextField(name="version"),
        ))
    timestamp = DateTimeField()


class PatientRecord(records.PatientRecord):
    """Patient Information Record (P)

    This record is used to transfer patient information to the analyzer (test
    order messages) or to the host (result messages).
    """
    name = TextField()
    birthdate = DateField()
    sex = TextField()


class OrderRecord(records.OrderRecord):

    sample_id = TextField()
    test = TextField()
    reported_at = DateTimeField()


class ResultRecord(records.ResultRecord):
    """Record to transmit analytical data.
    """
    test = TextField()
    value = TextField()
    status = TextField()
    completed_at = DateTimeField()


class TerminatorRecord(records.TerminatorRecord):
    """Message Termination Record (L)
    """


@register_instrument
class BiomerieuxMiniVidas(Instrument):
    name = "biomerieux_mini_vidas"
    header_regex = HEADER_RX
    version = VERSION
    raw_data_regex = RAW_DATA_RX
    record_map = {
        "H": HeaderRecord,
        "P": PatientRecord,
        "O": OrderRecord,
        "R": ResultRecord,
        "L": TerminatorRecord,
    }

    def _to_timestamp(self, date, time):
        dt = datetime.now()
        if date:
            dt = datetime.strptime(u(date), "%m/%d/%y")
        if time:
            t = datetime.strptime(u(time), "%H:%M").time()
            dt = datetime.combine(dt, t)
        return dt.strftime("%Y%m%d%H%M%S")

    def handle_raw_data(self, protocol, data):
        """Synthesise a complete ASTM session from a single non-ASTM
        packet emitted by the miniVidas. Drives ``protocol`` directly.
        """
        parts = re.match(RAW_DATA_RX, data)
        if not parts:
            return NAK
        if not protocol.in_transfer_state:
            protocol.on_enq(ENQ)

        values = {k: (u(v) if v else "")
                  for k, v in parts.groupdict().items()}
        values["ts"] = self._to_timestamp(
            values.get("td"), values.get("tt"))

        frames = [
            fmt("1H|\\^&|||miniVidas^biomerieux^1.0.0|||||||||{ts}{CR}{ETX}",
                **values),
            fmt(
                "2P|1|||{pi}|{pn}||{pb}|{ps}||||||||||||||||||||||||||"
                "{CR}{ETX}",
                **values),
            fmt(
                "3O|1|{ci}||{rn}||||||||||||||||||{ts}||||||||{CR}{ETX}",
                **values),
            fmt(
                "4R|1|{rt}|{qn}|||{nc}||{ql}||{m4}||{ts}|{CR}{ETX}",
                **values),
            fmt("5L|1|N{CR}{ETX}"),
        ]
        messages = []
        for frame in frames:
            cs = utils.make_checksum(frame)
            messages.append(
                fmt("{STX}{frame}{cs}{CRLF}", frame=u(frame), cs=u(cs)))

        protocol.messages = messages
        protocol.on_eot(EOT)
        return None


INSTRUMENT = BiomerieuxMiniVidas()
