# -*- coding: utf-8 -*-

from senaite.astm import records
from senaite.astm.fields import ComponentField
from senaite.astm.fields import DateField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import IntegerField
from senaite.astm.fields import NotUsedField
from senaite.astm.fields import RepeatedComponentField
from senaite.astm.fields import SetField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component

VERSION = "1.0.0"

# Supports XN-550, XN-530, XN-450, XN-430, XN-350, XN-330, XN-150, XN-110
# Sysmex Corporation, Automated Hematology Analyzer XN-L series ASTM Host
# Interface Specifications, Revision 6, 2017
HEADER_RX = r".*XN-(550|530|450|430|350|330|150|110)\^"

PATIENT_SEXES = (
    "M",  # M: male
    "F",  # F: female
    "U",  # U: unknown
)

SAMPLE_ID_ATTRIBUTES = (
    "M",  # M: Manual input
    "A",  # A: Automatic assignment by analyzer
    "B",  # B: Barcode reader
    "C",  # C: Assignment by host computer
)

ACTION_CODES = (
    "N",  # M: Manual/initial analysis
    "A",  # A: Rerun/reflex analayis
    "Q",  # Q: QC analysis
)

REPORT_TYPES = (
    "F",  # F: Manual analysis. Analysis other than repeat
    "I",  # I: Repeat analysis
    "X",  # X: Analysis not performed
    "Y",  # Y: No order
    "Q",  # Q: Response to inquiry
)

RESULT_DILUTION_RATIOS = (
    1,  # 1: Non-capillary
    5,  # 5: Capillary
)

RESULT_ABNORMAL_FLAGS = (
    "L",   # L: Lower than patient limit
    "H",   # H: Higher than patient limit
    ">",   # >: Out of assured linearity
    "N",   # N: Normal
    "A",   # A: Analysis/Hardware error
    "W",   # W: Low reliability
    "LL",  # LL: Lower than panic value
    "HH",  # HH: Higher than panic value
)

RESULT_STATUSES = (
    # Indicates judgement based on Repeat/Rerun/Reflex rule:
    "F",  # F: None
    "I",  # I: Repeat
    "P",  # P: Rerun or Reflex
    "N",  # N: Query to host
)

STATUS_CODES = (
    "F",  # F: Real-time inquiry (manual analysis) or batch inquiry
    "N",  # N: Real-time inquiry (sampler analysis) for initial analysis
    "C",  # C: Real-time inquiry (sampler analysis) for re-analysis
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
            TextField(name="name", default="XN"),
            TextField(name="version"),
            TextField(name="analyser_serial_no"),
            NotUsedField(name='_'),
            NotUsedField(name='__'),
            NotUsedField(name='___'),
            TextField(name="ps_code")
        ))

    processing_id = NotUsedField()
    version = TextField()


class PatientRecord(records.PatientRecord):
    """Patient Information Record (P)
    """
    id = TextField()
    name = ComponentField(
        Component.build(
            NotUsedField("_"),
            TextField(name="first_name"),
            TextField(name="last_name"),
        )
    )

    birthdate = DateField()
    sex = SetField(values=PATIENT_SEXES)
    physician_id = ComponentField(
        Component.build(
            NotUsedField("_"),
            TextField(name="physician_name")
        )
    )

    location = ComponentField(
        Component.build(
            NotUsedField("_"),
            NotUsedField("__"),
            NotUsedField("___"),
            TextField("ward"),
        )
    )


class OrderRecord(records.OrderRecord):
    """Order Record (O)
    """
    # Note the field "Sample ID" is not used, but the "Instrument Specimen ID"
    instrument = ComponentField(
        Component.build(
            TextField(name="sampler_adaptor_number", default=""),
            TextField(name="sampler_adaptor_position", default=""),
            TextField(name="sample_id"),
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
    report_type = SetField(values=REPORT_TYPES)


class CommentRecord(records.CommentRecord):
    """Comment Record (C)
    """
    data = TextField()


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
            TextField(name="result_type"),
            TextField(name="extended_order_result"),
        )
    )
    value = TextField(default="")
    units = TextField(default="")
    abnormal_flag = SetField(values=RESULT_ABNORMAL_FLAGS)
    status = SetField(values=RESULT_STATUSES)
    completed_at = DateTimeField()


class RequestInformationRecord(records.RequestInformationRecord):
    """Request information Record (Q)
    """
    starting_range = ComponentField(
        Component.build(
            TextField(name="sampler_adaptor_number"),
            TextField(name="sampler_adaptor_position"),
            TextField(name="sample_id"),
            SetField(name="sample_id_attr", values=SAMPLE_ID_ATTRIBUTES)
        )
    )
    beginning_results = DateTimeField()
    status_code = SetField(values=STATUS_CODES)


class ManufacturerInfoRecord(records.ManufacturerInfoRecord):
    """Manufacturer Specific Records (M)
    """


class TerminatorRecord(records.TerminatorRecord):
    """Message Termination Record (L)
    """
