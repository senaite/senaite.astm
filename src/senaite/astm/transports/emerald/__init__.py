# -*- coding: utf-8 -*-
"""Transport for the Abbott CELL-DYN Emerald family of hematology
analyzers (Emerald 18, Emerald 22 and Emerald 22 AL).

These instruments do not speak ASTM nor HL7, but a proprietary,
text-oriented protocol over TCP/IP (or RS232), as described in the
*CELL-DYN Emerald 22 AL Laboratory Information System Interface
Specification* (Abbott part no. 9159915, Rev. B). The instrument is
the TCP client: it connects to the host (this listener) and expects
an acknowledge for each frame when handshake mode is enabled.
"""
