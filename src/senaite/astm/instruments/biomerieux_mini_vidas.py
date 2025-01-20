# -*- coding: utf-8 -*-

from senaite.astm import records
from senaite.astm.fields import ComponentField, DateField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component

VERSION = "1.0.0"
# Supports Biomérieux miniVidas
HEADER_RX = r".*miniVidas\^"


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
        "P": PatientRecord,
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
