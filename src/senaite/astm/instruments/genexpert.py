# -*- coding: utf-8 -*-

from datetime import datetime

from senaite.astm import records
from senaite.astm.fields import ComponentField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import RepeatedComponentField
from senaite.astm.fields import SetField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component

VERSION = "1.0.0"

# GeneXpert LIS Interface Protocol Specification, 302-2261 Rev. E, 2022
# For Cepheid Software versions:
# - GeneXpert DX v4.7b and above
# - GeneXpert Omni Mobile Application 1.2 and above
# - GeneXpert Xpress 5.1 and above
# - Infinity Xpertise v6.4b and above
# - Cepheid OS 1.0 (GeneXpert® System with Touchscreen) and above
HEADER_RX = r".*(GeneXpert)\^"

PRIORITIES = (
    "S",  # S: Stat
    "R",  # R: Normal
)

ACTION_CODES = (
    "A",  # A: Some but not all results available
    "I",  # I: No results available
    "X",  # X: Result cannot be done, canceled
    "F",  # F: Final results
)

REPORT_TYPES = (
    "Q",  # Q: Request to query
    "X",  # X: Order cannot be done, canceled
    "I",  # I: Pending in system
    "F",  # F: Final results
    "Y",  # Y: Invalid Test ID
    "Z",  # Z: Invalid Patient ID
    "V",  # V: Invalid Specimen Identification
    "E",  # E: The query has a bad format
)

RESULT_ABNORMAL_FLAGS = (
    "<",  # <: below absolute low, that is off low scale on an instrument
    ">",  # >: above absolute high, that is off high scale on an instrument
    "N",  # N: normal
    "A",  # A: abnormal

    # Support for rev.E, 2014
    "L",  # L: below low normal
    "H",  # H: above high normal
    "LL",  # LL: below panic normal
    "HH",  # HH: above panic high
    "U",  # U: significant change up
    "D",  # D: significant change down
    "B",  # B: better, use when direction not relevant or not defined
    "W",  # W: worse, use when direction not relevant or not defined
)

RESULT_STATUSES = (
    "F",  # F: Final Result
    "I",  # I: Pending Result
    "X",  # X: Result cannot be done
    "C",  # C: Correction of previous result
)

COMMENT_IDS = (
    "Notes",
    "Error"
)

COMMENT_TYPES = (
    "I",  # I: Notes,
    "N",  # N: Error
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
    # Default delimiters: |@^\
    # - Field delimiter – vertical bar (ASCII 124)( | ) Latin-1 (124)
    # - Repeat delimiter – at (ASCII 64)( @ ) Latin-1 (64)
    # - Component delimiter – caret (ASCII 94)( ^ ) Latin-1 (94)
    # - Escape delimiter – backslash (ASCII 92)( \ ) Latin-1 (92)
    # E.g. H|@^\|12X||GeneXpert PC^Xpert^6.1|||||LIS||P|1394-97|20190521100245
    delimeter = RepeatedComponentField(
        Component.build(
            TextField(name="_", default=""),
            TextField(name="__")
        ), default=[[], ["@", ""]]
    )

    # Message ID: Uniquely identifies the message
    message_id = TextField()

    # Sender Name or ID
    sender = ComponentField(
        Component.build(
            TextField(name="id"),
            TextField(name="name", default="GeneXpert"),
            TextField(name="software_version", ),
        ))

    # Receiver ID
    receiver = TextField()
    version = TextField(default="1394-97")


class PatientRecord(records.PatientRecord):
    """Patient Information Record (P)
    """
    # Practice Assigned Patient ID. (This field is not sent in Service Mode 1.)
    practice_id = TextField()
    laboratory_id = TextField()
    id = TextField()

    # Component Field: <last name>^<first name> (patient samples only,
    # only if entered, not in Manufacturing Mode 1)(This field is not sent in
    # Service Mode 1)
    name = ComponentField(
        Component.build(
            TextField(name="family_name"),
            TextField(name="given_name"),
            TextField(name="middle_name"),
            TextField(name="prefix"),
            TextField(name="suffix"),
        )
    )


class OrderRecord(records.OrderRecord):
    """Order Record (O)
    """
    sample_id = TextField(required=True)
    instrument = TextField()
    priority = SetField(values=PRIORITIES, default="R")
    requested_at = DateTimeField(default=datetime.now)
    action_code = SetField(values=ACTION_CODES)
    # ORH ('Other' according to POCT1-A standard)
    biomaterial = TextField(default="ORH")
    report_type = SetField(values=REPORT_TYPES)


class CommentRecord(records.CommentRecord):
    """Comment Record (C)
    """
    source = TextField(default="I")
    data = ComponentField(
        Component.build(
            SetField(name="id", values=COMMENT_IDS),
            TextField(name="code"),
            TextField(name="description"),
        )
    )
    ctype = SetField(values=COMMENT_TYPES)


class ResultRecord(records.ResultRecord):
    """Record to transmit analytical data.
    """
    # 3: Universal Test ID
    test = ComponentField(
        Component.build(
            TextField(name="_"),
            # Empty for a single result test.
            # Assay panel ID for a multi-result test.
            TextField(name="panel_id"),
            TextField(name="___"),
            # For single-result test, this is the Assay Host Test Code.
            # For multi-result test, this is the Result test code in system
            # configuration.
            TextField(name="test_id", required=True),
            # The assay name shown in system configuration (only at main result
            # for single result or multi-result test);
            # Empty for analyte or complementary results.
            TextField(name="test_name"),
            # The assay version shown in system configuration (only at main or
            # one of the multi-results)
            TextField(name="test_version"),
            # Possible values: Result Test Code for a main result in
            # multi-result test.
            # Empty: for a main result in single-result test.
            # Analyte Name: for analyte result or complementary result
            TextField(name="analyte_name"),
            # Only used for complementary results (otherwise it is empty).
            # Possible values: ‘Ct’/’EndPt’/ ’Delta Ct’/ ’Conc/LOG’
            # Empty for main result or analyte result.
            TextField(name="complementary_name")
        )
    )

    # 4: Data or Measurement Value
    value = ComponentField(
        Component.build(
            # Observed, calculated or implied result value (Qualitative)
            # Error message if test with error. (i.e. Field 9 = ‘X’)
            TextField(name="qualitative_result"),
            # Observed, calculated or implied result value (Quantitative)
            TextField(name="quantitative_result")
        )
    )

    # 5: Units. Abbreviation of units for numerical results
    units = TextField()

    # 6: Reference Ranges
    # Lower limit to upper limit; example: “3.5 to 4.5”
    # If no lower limit: “to 4.5”
    # If no upper limit: “3.5 to”
    # Only present if the result is the main one and there is a quantitative
    # result.
    references = TextField()

    # 7: Result Abnormal Flags
    abnormal_flag = SetField(values=RESULT_ABNORMAL_FLAGS)

    # 9: Status
    status = SetField(values=RESULT_STATUSES)

    # 11: Operator fullname
    operator = TextField()

    # 12 Date Time Test started
    started_at = DateTimeField()

    # 13 Date Time Test Completed
    completed_at = DateTimeField()

    # 14 Instrument Identification
    instrument = ComponentField(
        Component.build(
            # Identifies the PC connected to the instrument
            TextField(name="system_name"),
            # Identifies the instrument that performed this measurement
            TextField(name="instrument_sn"),
            # Identifies the module that performed this measurement
            TextField(name="module_sn"),
            # Identifies the cartridge that performed this measurement
            TextField(name="cartridge"),
            # Reagent Lot ID
            TextField(name="reagent_lot"),
            # Expiration date
            TextField(name="expiration_date"),
        )
    )


class RequestInformationRecord(records.RequestInformationRecord):
    """Request information Record (Q)
    """


class ManufacturerInfoRecord(records.ManufacturerInfoRecord):
    """Manufacturer Specific Records (M)
    """


class TerminatorRecord(records.TerminatorRecord):
    """Message Termination Record (L)
    """
