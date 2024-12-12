# -*- coding: utf-8 -*-

from senaite.astm import records
from senaite.astm.fields import ComponentField
from senaite.astm.fields import ConstantField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import IntegerField
from senaite.astm.fields import NotUsedField
from senaite.astm.fields import SetField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component

VERSION = "1.0.0"
HEADER_RX = r".*Afinion 2 Analyzer\^"

PROCESSING_IDS = (
    "P",  # P: Patient measurement results
    "Q",  # Q: Quality control results
)

SPECIMEN_SOURCES = (
    "O",  # O: Other
    "C",  # C: Blood capillary
    "V",  # V: Blood venous
)

ABNORMAL_FLAGS = (
    "<",   # <: Less than measurement lower limit
    ">",   # >: Higher than measurement upper limit
    "L",   # L: Less than normal range
    "H",   # H: Higher than normal range
    "LL",  # LL: Less than extreme range
    "HH",  # HH: Higher than extreme range
    "!",   # !: Result ambiguous
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
        "Q": RequestInformationRecord,
        "M": ManufacturerInfoRecord,
        "L": TerminatorRecord,
    }


class HeaderRecord(records.HeaderRecord):
    """Message Header Record (H)

    This record must always be the first record in a transmission. This record
    contains information about the sender and receiver, instruments, and
    computer system whose records are being exchanged. It also identifies the
    delimiter characters. The minimum information that must be sent in a Header
    record is: H|\^&{RT}

    Example:
    H|\^&|||Afinion 2 Analyzer^^AF0000030|||||EPR||P|1|20100608185448|
    """
    sender = ComponentField(
        Component.build(
            # H.5.1 Model name (always "Afinion 2 Analyzer")
            TextField(name="name"),
            NotUsedField(name="_"),
            # H.5.3 DeviceID of measuring device
            TextField(name="serial"),
        ))

    # H.10.1 Name of the receiving application / dept.
    receiver = TextField()
    # H.12.1 Processing ID
    processing_id = SetField(values=PROCESSING_IDS)
    # H.13.1 ASTM-version used
    version = TextField()


class PatientRecord(records.PatientRecord):
    """Patient Information Record (P)

    This record is used to transfer patient information to the analyzer (test
    order messages) or to the host (result messages).

    Example:
    P|1||43|||||U|
    """
    # P.4.1 (local) patient ID
    laboratory_id = TextField()


class OrderRecord(records.OrderRecord):
    """Order Record (O)

    Example:
    O|1||43|^^^CRP|||||||N||||^O||||||||^10124809||F|
    """
    # O.4.1 Filler order number
    instrument = IntegerField()

    # O.5.4 Name of assay (e.g. CRP, ACR, Lipid Panel, HbA1C, ...)
    test = ComponentField(
        Component.build(
            NotUsedField(name="_"),
            NotUsedField(name="__"),
            NotUsedField(name="___"),
            TextField(name="name")
        )
    )

    # O.12.1 Specimen action code
    action_code = ConstantField(default="N")

    # O.16.2 Specimen Source
    biomaterial = ComponentField(
        Component.build(
            NotUsedField(name="_"),
            SetField(name="source", values=SPECIMEN_SOURCES)
        )
    )


class CommentRecord(records.CommentRecord):
    """Comment Record (C)
    """


class ResultRecord(records.ResultRecord):
    """Record to transmit analytical data.

    Examples:
    R|1|^^^CRP|16|mg/L||||F||||20100608142352|
    R|1|^^^ACR|<5.6|mg/g||<||F||||20100608140536|
    R|1|^^^ACR|--- |mg/g||||F||||20100608140626|
    R|1|^^^HbA1c|>15.0|%||>||F||||20201201142122|
    """

    test = ComponentField(
        Component.build(
            NotUsedField("_"),
            NotUsedField("__"),
            NotUsedField("___"),
            # R.3.4 Test Name (e.g. CRP, Alb, Creat, Trig, Chol, HbA1c, ..)
            TextField("name")
        )
    )

    # R.4.1 Measurement value
    value = TextField()

    # R.5.1 Units
    units = TextField()

    # R.7.1 Abnormal flags
    # Precaution for results outside the measuring range:
    # Calculated and measured results outside the measuring range are indicated
    # with a comparator flag,">" or "<", passed along with a value in the
    # observation value field. If the calculation is not possible, or the
    # concentration can't be measured, the observation value field will contain
    # "--- " instead of a value
    abnormal_flag = SetField(values=ABNORMAL_FLAGS)

    # R.9.1 Observation result status. Always "F" (final result)
    status = ConstantField(default="F")

    # R.11.1 Operator ID of the user, which the measurement has done
    operator = TextField()

    # R.13.1: Measurement time
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
