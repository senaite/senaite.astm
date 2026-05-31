# -*- coding: utf-8 -*-
"""Synthesize a full ASTM session from a list of frame templates.

Used by adapters whose wire format is not valid ASTM
(``biomerieux_mini_vidas``, ``spotchem_el``): the device sends a
single non-ASTM packet, the adapter decodes it into a list of
pre-numbered frame templates ending in ``{CR}{ETX}``, and this
helper handles the shared boilerplate of:

- starting the session with ENQ if the protocol is idle,
- wrapping each frame in ``STX`` + checksum + ``CRLF``,
- queueing them on ``protocol.messages``,
- closing the session with EOT.

This keeps the per-instrument code focused on its own decoding
logic instead of repeating the framing dance.
"""

from senaite.astm import utils
from senaite.astm.constants import ENQ, EOT


def synthesize_session(protocol, frames):
    """Drive ``protocol`` through a complete synthetic ASTM session.

    :param protocol: An :class:`ASTMProtocol` instance.
    :param frames: A list of pre-formatted frame templates (each
        already contains its sequence number and ``{CR}{ETX}``).
    """
    if not protocol.in_transfer_state:
        protocol.on_enq(ENQ)
    messages = []
    for frame in frames:
        cs = utils.make_checksum(frame)
        messages.append(
            utils.f("{STX}{frame}{cs}{CRLF}",
                    frame=utils.u(frame), cs=utils.u(cs)))
    protocol.messages = messages
    protocol.on_eot(EOT)
