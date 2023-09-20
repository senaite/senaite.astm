# -*- coding: utf-8 -*-

from senaite.astm import records
from senaite.astm.fields import ComponentField
from senaite.astm.fields import NotUsedField
from senaite.astm.fields import SetField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component

# Supports H500 and H550
HEADER_RX = r".*H5[0,5]0\^"


def get_mapping():
    """Returns the wrappers for this instrument
    """
    return {
        "H": HeaderRecord,
        "P": PatientRecord,
        "O": OrderRecord,
        "R": ResultRecord,
        "C": CommentRecord,
        "Q": RequestInformationRecord,
        "M": ManufacturerInfoRecord,
        "L": TerminatorRecord,
    }


class HeaderRecord(records.HeaderRecord):
    """Message Header Record (H)
    """
    sender = ComponentField(
        Component.build(
            TextField(name="name"),
            TextField(name="serial"),
            TextField(name="version"),
        ))

    processing_id = SetField(
        field=TextField(),
        # P: Patient message, Q: Quality control message, D: Technician
        values=("P", "Q", "D"))

    version = TextField()


class PatientRecord(records.PatientRecord):
    """Patient Information Record (P)
    """
    unknown_1 = NotUsedField()
    unknown_2 = NotUsedField()


class OrderRecord(records.OrderRecord):
    """Order Record (O)
    """


class CommentRecord(records.CommentRecord):
    """Comment Record (C)
    """


class ResultRecord(records.ResultRecord):
    """Record to transmit analytical data.
    """


class RequestInformationRecord(records.RequestInformationRecord):
    """Request information Record (Q)
    """


class ManufacturerInfoRecord(records.ManufacturerInfoRecord):
    """Manufacturer Specific Records (M)
    """


class TerminatorRecord(records.TerminatorRecord):
    """Message Termination Record (L)
    """
