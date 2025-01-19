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
    rb"\x02"                                     # Start of the message
    rb"(?:\x1emt(?P<mt>[^|]*))?"                 # Message Type (mt)
    rb"(?:\|\x1epi(?P<pi>[^|]*))?"               # Patient Identifier (pi)
    rb"(?:\|\x1epn(?P<pn>[^|]*))?"               # Patient Name (pn)
    rb"(?:\|\x1epb(?P<pb>[^|]*))?"               # Patient Birthdate (pb)
    rb"(?:\|\x1eps(?P<ps>[^|]*))?"               # Patient Sex (ps)
    rb"(?:\|\x1eso(?P<so>[^|]*))?"               # Sample Origin (so)
    rb"(?:\|\x1esi(?P<si>[^|]*))?"               # Specimen separator (si)
    rb"(?:\|\x1eci(?P<ci>[^|]*))?"               # Sample Identifier (ci)
    rb"(?:\|\x1ert(?P<rt>[^|]*))?"               # Short assay name (rt)
    rb"(?:\|\x1ern(?P<rn>[^|]*))?"               # Long assay name (rn)
    rb"(?:\|\x1ett(?P<tt>[^|]*))?"               # Test completion time (tt)
    rb"(?:\|\x1etd(?P<td>[^|]*))?"               # Test completion date (td)
    rb"(?:\|\x1eql(?P<ql>[^|]*))?"               # Qualitative Result (ql)
    rb"(?:\|\x1eqn(?P<qn>[^|]*))?"               # Quantitative Result (qn)
    rb"(?:\|\x1ey3(?P<y3>[^|]*))?"               # Unit associated with qn (y3)
    rb"(?:\|\x1eqd(?P<qd>[^|]*))?"               # Dilution (qd)
    rb"(?:\|\x1enc(?P<nc>[^|]*))?"               # Vidas flags (nc)
    rb"(?:\|\x1eid(?P<id>[^|]*))?"               # Instrument ID (id)
    rb"(?:\|\x1esn(?P<sn>[^|]*))?"               # Serial Number (sn)
    rb"(?:\|\x1em4(?P<m4>[^|]*))?"               # Technologist (m4)
    rb"(?:\|\x1d(?P<checksum>[a-fA-F0-9]{2}))$"  # Checksum
)


@implementer(IDataHandler)
class DataHandler:
    """Custom data handler for Biomérieux miniVidas

    We receive from this instrument a non valid ASTM message that need to be
    handled differntly
    """
    def __init__(self, protocol, data):
        self.protocol = protocol
        self.data = data

    def can_handle(self):
        return re.match(RX, self.data) is not None

    def to_timestamp(self, date, time):
        """Make a timestamp from the date and time
        """
        dt = datetime.now()
        if date:
            dt = datetime.strptime(u(date), '%m/%d/%y')
        if time:
            t = datetime.strptime(u(time), '%H:%M').time()
            dt = datetime.combine(dt, t)
        return dt.strftime("%Y%m%d%H%M%S")

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

        data = {}
        for k, v in parts.groupdict().items():
            data[k] = u(v) if v else ""

        # convert date and time to a timestamp
        date = data.get("td")
        time = data.get("tt")
        data["ts"] = self.to_timestamp(date, time)

        frames = [
            f("1H|\\^&|||miniVidas^biomerieux^1.0.0|||||||||{ts}{CR}{ETX}",
              **data),
            f("2P|1|||{pi}|{pn}||{pb}|{ps}||||||||||||||||||||||||||{CR}{ETX}",
              **data),
            f("3O|1|{ci}||{rn}||||||||||||||||||{ts}||||||||{CR}{ETX}",
              **data),
            f("4R|1|{rt}|{qn}|||{nc}||{ql}||{m4}||{ts}|{CR}{ETX}",
              **data),
            f("5L|1|N{CR}{ETX}"),
        ]
        messages = []
        for frame in frames:
            cs = utils.make_checksum(frame)
            messages.append(
                f("{STX}{frame}{cs}{CRLF}", frame=u(frame), cs=u(cs)))

        # fill in the full message
        self.protocol.messages = messages

        # end the communicaiton
        # self.protocol.on_eot(EOT)


# register the adapter
adapter_registry.registerAdapter(
    DataHandler,
    required=(object, object),
    provided=IDataHandler,
    name="mini_vidas",
)
