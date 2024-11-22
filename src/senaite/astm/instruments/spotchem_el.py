# -*- coding: utf-8 -*-

from senaite.astm import records
from senaite.astm.fields import ComponentField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component

VERSION = "1.0.0"
# Supports SE1520
HEADER_RX = r".*SE-1520\^"


def get_metadata(wrapper):
    """Additional metadata

    :param wrapper: The wrapper instance
    :returns: dictionary of additional metadata
    """
    return {
        "version": VERSION,
        "header_rx": HEADER_RX,
    }


def get_mapping():
    """Returns the wrappers for this instrument
    """
    return {
        "H": HeaderRecord,
        "O": OrderRecord,
        "R": ResultRecord,
        "L": TerminatorRecord,
    }


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
