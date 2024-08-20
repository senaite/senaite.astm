# -*- coding: utf-8 -*-

from senaite.astm import records
from senaite.astm.fields import ComponentField
from senaite.astm.fields import ConstantField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import IntegerField
from senaite.astm.fields import NotUsedField
from senaite.astm.fields import RepeatedComponentField
from senaite.astm.fields import SetField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component

VERSION = "1.0.0"

# Supports XP-100 or XP-300
# Sysmex Corporation, XP Series ASTM Communication Specifications (ASTM
# E1394-97, E1381-02/94), Revision 1.0, 2012
HEADER_RX = r".*XP-(100|300)\^"

SAMPLE_ID_ATTRIBUTES = (
    "M",  # M: Manual input
    "A",  # A: Automatic assignment
    "B",  # B: Read by ID reader
)

ACTION_CODES = (
    "N",  # M: Normal sample data
    "Q",  # Q: QC data
)

RESULT_DILUTION_RATIOS = (
    1,  # 1: Whole blood mode
    26,  # 26: Diluent mode
)

RESULT_ABNORMAL_FLAGS = (
    "L",   # L: “-” flagged data
    "H",   # H: “+” flagged data
    ">",   # >: “!” flagged data
    "N",   # N: Normal data
    "A",   # A: Masked data
    "W",   # W: “*” flagged data
)


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
            TextField(name="name", default="XP"),
            TextField(name="version"),
            NotUsedField(name='_'),
            NotUsedField(name='__'),
            NotUsedField(name='___'),
            TextField(name="device_number"),
            TextField(name="ps_code")
        ))

    processing_id = NotUsedField()
    version = TextField()


class PatientRecord(records.PatientRecord):
    """Patient Information Record (P)
    """


class OrderRecord(records.OrderRecord):
    """Order Record (O)
    """
    # Note the field "Sample ID" is not used, but the "Instrument Specimen ID"
    instrument = ComponentField(
        Component.build(
            NotUsedField("_"),
            NotUsedField("__"),
            # Sample numbers that are not 15 digits long are space padded or
            # zero padded to 15 digits as specified by the ID Pad. setting in
            # Settings-Host output setting
            TextField(name="sample_id", length=15),
            SetField(name="sample_id_attr", values=SAMPLE_ID_ATTRIBUTES)
        )
    )

    test = RepeatedComponentField(
        Component.build(
            NotUsedField("_"),
            NotUsedField("__"),
            NotUsedField("___"),
            NotUsedField("____"),
            TextField("parameter"),
        )
    )
    action_code = SetField(values=ACTION_CODES)
    report_type = ConstantField(default="F")


class CommentRecord(records.CommentRecord):
    """Comment Record (C)
    """


class ResultRecord(records.ResultRecord):
    """Record to transmit analytical data.
    """
    test = ComponentField(
        Component.build(
            TextField(name="_"),
            TextField(name="__"),
            TextField(name="___"),
            TextField(name="____"),
            TextField(name="parameter"),
            SetField(name="dilution_ratio",
                     field=IntegerField(),
                     values=RESULT_DILUTION_RATIOS),
        )
    )
    value = TextField(default="")
    units = TextField(default="")
    abnormal_flag = SetField(values=RESULT_ABNORMAL_FLAGS)
    # Operator Identification. (A 15-character ID that is left aligned and
    # padded with spaces). Example: “ABCDEFGHI      “
    operator = TextField(length=15)
    completed_at = DateTimeField()


class RequestInformationRecord(records.RequestInformationRecord):
    """Request information Record (Q)
    """


class ManufacturerInfoRecord(records.ManufacturerInfoRecord):
    """Manufacturer Specific Records (M)
    """


class TerminatorRecord(records.TerminatorRecord):
    """Message Termination Record (L)
    """
