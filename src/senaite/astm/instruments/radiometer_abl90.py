# -*- coding: utf-8 -*-

import re

from senaite.astm import records
from senaite.astm.core.instrument import Instrument
from senaite.astm.core.instrument import register_instrument
from senaite.astm.fields import ComponentField
from senaite.astm.fields import DateField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import NotUsedField
from senaite.astm.fields import SetField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component

VERSION = "1.0.0"
HEADER_RX = re.compile(rb".*ABL9\d+")

#: O.16 Specimen descriptor. The sample type decides which analysis the
#: result belongs to, because the same analyte is reported as a different
#: service depending on where the blood was drawn from
SPECIMEN_TYPES = (
    "Arterial",
    "Venous",
    "Capillary",
    "Mixed-venous",
    "Not specified",
)

#: R.3.5 Parameter type. A parameter is reported no matter how its value was
#: obtained, so none of these may be filtered out downstream
PARAMETER_TYPES = (
    "C",  # C: Calculated parameter
    "D",  # D: Default parameter
    "E",  # E: Estimated parameter
    "I",  # I: Input parameter, keyed in by the operator
    "M",  # M: Measured parameter
    "",   # Parameter type not specified
)

#: R.7 Result abnormal flags
ABNORMAL_FLAGS = (
    "N",   # N: Normal value
    "L",   # L: Below low normal range
    "H",   # H: Above high normal range
    "LL",  # LL: Below low critical range
    "HH",  # HH: Above high critical range
    "<",   # <: Below the measuring range of the analyzer
    ">",   # >: Above the measuring range of the analyzer
)

#: R.9 Result status
RESULT_STATUS = (
    "F",  # F: Final result
    "C",  # C: Corrected result, only with Audit Trail enabled
    "R",  # R: Retransmitted and not corrected, only with Audit Trail enabled
)


class HeaderRecord(records.HeaderRecord):
    """Message Header Record (H)

    Example:
    H|\\^&|||ABL90 FLEX PLUS^Blood Gas||||||||1|20261019103012
    """

    sender = ComponentField(
        Component.build(
            # H.5.1 Analyzer model, e.g. "ABL90 FLEX PLUS"
            TextField(name="name"),
            # H.5.2 Department the analyzer is assigned to
            TextField(name="department"),
        ))

    # H.12 Processing ID. Left empty by the analyzer
    processing_id = TextField()

    # H.13 ASTM version number
    version = TextField()


class PatientRecord(records.PatientRecord):
    """Patient Information Record (P)

    Every identification below is keyed in at the analyzer, so any of them
    can be empty.

    Example:
    P|1||P000123||Doe^Jane||19800115|F|||||||32^years||1.68^m|62.0^kg||||||||
    """

    # P.4 Patient ID
    laboratory_id = TextField()

    # P.6 Patient name
    name = ComponentField(
        Component.build(
            TextField(name="last_name"),
            TextField(name="first_name"),
        ))

    # P.8 Date of birth (YYYYMMDD)
    birthdate = DateField()

    # P.9 Sex
    sex = TextField()

    # P.15 Age and its unit ("years" or "months"). The analyzer sends the age
    # that was keyed in, which is not necessarily derived from the birthdate
    special_1 = ComponentField(
        Component.build(
            TextField(name="age"),
            TextField(name="unit"),
        ))

    # P.17 Height and its unit ("cm" or "ft:inc")
    height = ComponentField(
        Component.build(
            TextField(name="value"),
            TextField(name="unit"),
        ))

    # P.18 Weight and its unit ("kg" or "pound")
    weight = ComponentField(
        Component.build(
            TextField(name="value"),
            TextField(name="unit"),
        ))


class OrderRecord(records.OrderRecord):
    """Order Record (O)

    Example:
    O|1|WB-0001|Sample #^1442|^^^syringe|||20261019102955||||||||Blood^Arteri
    al|||||||||||F

    O.3 carries the sample ID that was keyed in at the analyzer, while O.4
    carries the sequence number the analyzer assigns to every measurement on
    its own. Both are sent, and only O.3 can be matched against the LIMS.
    """

    # O.3 Specimen ID, the sample ID keyed in at the analyzer
    sample_id = TextField()

    # O.4 Instrument specimen ID, e.g. "Sample #^1442"
    instrument = ComponentField(
        Component.build(
            TextField(name="label"),
            TextField(name="number"),
        ))

    # O.5 Universal test ID, holding the measuring mode, e.g. "^^^syringe"
    test = ComponentField(
        Component.build(
            NotUsedField(name="_"),
            NotUsedField(name="__"),
            NotUsedField(name="___"),
            TextField(name="mode"),
        ))

    # O.8 Sampling time
    sampled_at = DateTimeField()

    # O.16 Specimen descriptor. The two components are not ordered the same
    # way across the analyzer families: some send "<sample type>^<sample
    # site>" and others "Blood^<sample type>", so the sample type has to be
    # looked for in both
    biomaterial = ComponentField(
        Component.build(
            TextField(name="specimen_type"),
            TextField(name="specimen_source"),
        ))

    # O.26 Report type
    report_type = TextField()


class CommentRecord(records.CommentRecord):
    """Comment Record (C)

    A comment always refers to the record before it: sent before the first R
    record it is a general condition of the analyzer, and sent after an R
    record it is an error or a flag on that parameter.

    Example:
    C|1|I|377^Calibration drift out of range|I
    """

    # C.3 Comment source, always "I" for the clinical instrument system
    source = TextField()

    # C.4 Comment text, the error code and optionally its description
    data = ComponentField(
        Component.build(
            TextField(name="code"),
            TextField(name="description"),
        ))

    # C.5 Comment type
    ctype = TextField()


class ResultRecord(records.ResultRecord):
    """Record to transmit analytical data

    Examples:
    R|1|^^^pH^M|7.402|||N||F||LABG|20261019103012
    R|3|^^^pO2^M|?92.4|mmHg||N||F|||
    R|4|^^^HCO3-^C|24.8|mmol/L||N||F|||

    Note R.12 is the only time stamp the analyzer sends, R.13 is never used,
    and R.12 is only sent with the first result record of the message. A
    consumer that reads the capture date from each record on its own
    therefore finds one on the first result and none on the rest.
    """

    # R.3 Universal test ID. The parameter name is the identifier to map to a
    # service, and its spelling is the one of the "ASTM/HL7" column of the
    # list of parameters, which is not always the name shown on screen: the
    # base excess of extracellular fluid, cBase(Ecf), is sent as "SBE"
    test = ComponentField(
        Component.build(
            NotUsedField(name="_"),
            NotUsedField(name="__"),
            NotUsedField(name="___"),
            TextField(name="name"),
            SetField(name="parameter_type", values=PARAMETER_TYPES),
        ))

    # R.4 Measurement value. It is prefixed with a "?" when the analyzer
    # flagged an error on the parameter, so it is not always floatable
    value = TextField()

    # R.5 Units
    units = TextField()

    # R.7 Result abnormal flags
    abnormal_flag = SetField(values=ABNORMAL_FLAGS)

    # R.9 Result status
    status = SetField(values=RESULT_STATUS)

    # R.11 Operator ID, only sent with the first result record
    operator = TextField()

    # R.12 Date/time the analysis was completed, despite the name the
    # standard gives this field. Only sent with the first result record
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


@register_instrument
class RadiometerABL90(Instrument):
    """Radiometer ABL90 FLEX and ABL90 FLEX PLUS blood gas analyzers
    """
    name = "radiometer_abl90"
    header_regex = HEADER_RX
    version = VERSION
    record_map = {
        "H": HeaderRecord,
        "P": PatientRecord,
        "O": OrderRecord,
        "R": ResultRecord,
        "C": CommentRecord,
        "Q": RequestInformationRecord,
        "M": ManufacturerInfoRecord,
        "L": TerminatorRecord,
    }


INSTRUMENT = RadiometerABL90()
