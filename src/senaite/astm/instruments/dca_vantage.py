# -*- coding: utf-8 -*-

from senaite.astm import records
from senaite.astm.fields import ComponentField
from senaite.astm.fields import ConstantField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import NotUsedField
from senaite.astm.fields import SetField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component

VERSION = "1.0.0"

# Siemens Healthcare Diagnostics, DCA Vantage® Analyzer, Host Computer
# Communications Link, 17306 Rev. E 2012-06, 2012
HEADER_RX = r".*(DCA VANTAGE|DCA Vantage)\^"

PROCESSING_IDS = (
    "P",  # P: Production (the message contains clinical results)
    "D",  # D: Debugging (the instrument is in service mode)
)

ACTION_CODES = (
    "Q",  # Q: when control is run, else unused
)

REPORT_TYPES = (
    "F",  # F: Final
    "C",  # C: Correction of previously transmitted results
)

RESULT_ABNORMAL_FLAGS = (
    "<",  # <: Below instrument measurement range
    ">",  # >: Above instrument measurement range
    "H",  # H: Above patient reference range or expected range of a control
    "L",  # L: Below patient reference range or expected range of a control
)

RESULT_STATUSES = (
    "F",  # F: Final Result
    "C",  # C: Correction of previously transmitted results
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
            TextField(name="name", default="DCA VANTAGE"),
            TextField(name="version"),
            TextField(name="serial"),
        ))

    processing_id = SetField(values=PROCESSING_IDS)


class PatientRecord(records.PatientRecord):
    """Patient Information Record (P)
    """
    # Practice Assigned Patient ID. (This field is not sent in Service Mode 1.)
    practice_id = TextField()

    # Component Field: <last name>^<first name> (patient samples only,
    # only if entered, not in Manufacturing Mode 1)(This field is not sent in
    # Service Mode 1)
    name = ComponentField(
        Component.build(
            TextField(name="last_name"),
            TextField(name="first_name"),
        )
    )


class OrderRecord(records.OrderRecord):
    """Order Record (O)
    """
    # Note the field "Sample ID" is not used, but the sample_seq_number.
    # Consider to better find matches by using patient record's practice_id
    instrument = ComponentField(
        Component.build(
            # Patient results: 001 through 999 (sample sequence number),
            # Reagent Lot Number
            # “<sample sequence number>^<reagent lot number>”
            TextField("sample_seq_num"),
            TextField("reagent_lot_num"),
        )
    )
    action_code = SetField(values=ACTION_CODES)
    report_type = SetField(values=REPORT_TYPES)


class CommentRecord(records.CommentRecord):
    """Comment Record (C)
    """
    # I: Clinical instrument system
    source = ConstantField(default="I")

    # Comment Text
    # 1-to-many record specific text strings, separated by a component
    # delimiter. The structure of this record depends on the type of record
    # processed before:
    # a) After the Order record for patient tests, transmit GFR data and
    #    Comment information (if entered)
    #    e.g. <age>^<gender>^<race>^<creatinine input>^<gfr result>^<c1>^<c2>
    # b) After HbA 1c results, transmit User Correction Slope, User Correction
    #    Offset, Primary Reporting Unit, and eAG (when available and enabled).
    #    The eAG reporting unit is either “mg/dL” or “mmol/L”.
    #    e.g. 1.000^0.0 <units>^NGSP^<eAG-value><eAG-units>
    # c) After Microalbumin and Creatinine results, transmit User Correction
    #    Slope and Offset
    #    e.g. C|1|I|1.000^0.0 <units>|G<CR>
    # d) After the order record for controls, transmit Comment Information (if
    #    entered,) (one for each comment entered) up to 3 comments).
    #    e.g. C|1|I|<c1>^<c2>^<c3>G<CR>
    # Therefore, we leave it as a NotUsedField to let the consumer deal with it
    data = NotUsedField()

    # G: General/Free text comment
    ctype = ConstantField(default="G")


class ResultRecord(records.ResultRecord):
    """Record to transmit analytical data.
    """
    test = ComponentField(
        Component.build(
            TextField(name="_"),
            TextField(name="__"),
            TextField(name="___"),
            TextField(name="parameter"),
        )
    )
    value = TextField(default="")
    units = TextField(default="")
    references = TextField(default="")
    abnormal_flag = SetField(values=RESULT_ABNORMAL_FLAGS)
    status = SetField(values=RESULT_STATUSES)
    operator = TextField()
    started_at = DateTimeField()


class RequestInformationRecord(records.RequestInformationRecord):
    """Request information Record (Q)
    """


class ManufacturerInfoRecord(records.ManufacturerInfoRecord):
    """Manufacturer Specific Records (M)
    """


class TerminatorRecord(records.TerminatorRecord):
    """Message Termination Record (L)
    """
