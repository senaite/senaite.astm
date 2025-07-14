# -*- coding: utf-8 -*-

from senaite.astm import records
from senaite.astm.fields import ComponentField
from senaite.astm.fields import ConstantField
from senaite.astm.fields import DateField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import IntegerField
from senaite.astm.fields import NotUsedField
from senaite.astm.fields import RepeatedComponentField
from senaite.astm.fields import SetField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component

VERSION = "1.0.0"
HEADER_RX = r".*ARCHITECT\^"

PROCESSING_IDS = (
    "P",  # P: Patient measurement results
    "Q",  # Q: Quality control results
)

PATIENT_GENDERS = (
    "M",  # M: Male
    "F",  # F: Female
    "U",  # U: Unknown
)

ASSAY_STATUSES = (
    "P",  # P: Assay is installed as the primary version
    "C",  # C: ASsay is installed as the correlation version
)

PRIORITIES = (
    "S",  # S: STAT
    "R",  # R: Routine
)

REPORT_TYPES = (
    "F",  # F: Final Result
    "X",  # X: Test could not be performed
)

RESULT_TYPES = (
    "F",  # F: Final Result concentration patient, or control result
    "P",  # P: Preliminary instrument result
    "I",  # I: Interpretation of final result for patient results
)

RESULT_STATUSES = (
    "F",  # F: Final Results
    "R",  # R: Previously Transmitted Results
)

COMMENT_TYPES = (
    "G",  # G: Result Comment
    "I",  # I: Exception String
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
    record is: H|\\^&{RT}

    Example:
    H|\^&|||ARCHITECT^1.00^123456789^H1P1O1R1C1Q1L1|||||||P|1|19930330133346
    """
    sender = ComponentField(
        Component.build(
            # H.5.1 Instrument Name
            TextField(name="name"),
            # H.5.2 Version number in the format 1.23
            TextField(name="version"),
            # H.5.3 SCC Serial Number
            TextField(name="serial"),
            # H.5.4 Record types the system supports
            TextField(name="interface"),
        ))
    # H.12 Processing ID
    processing_id = SetField(values=PROCESSING_IDS)
    # H.13 Version No.
    version = TextField()


class PatientRecord(records.PatientRecord):
    """Patient Information Record (P)

    This record is used to transfer patient information to the analyzer (test
    order messages) or to the host (result messages).

    Example:
    P|1|||PIDSID13|Patient^Im^A||19320122|F|||||Dr.Amesbury||||||||||||ParkClinic
    """
    # P.3 Practice-Assigned Patient ID
    practice_id = TextField()
    # P.4 Laboratory-Assigned Patient ID
    laboratory_id = TextField()
    # P.5 Patient ID
    id = TextField()
    # P.6 Patient Name
    name = ComponentField(
        Component.build(
            # P.6.1 Patient Last Name
            TextField(name="last"),
            # P.6.2 Patient First Name
            TextField(name="first"),
            # P.6.3 Patient Middle Name
            TextField(name="middle"),
        ))
    # P.8 Birth date
    birthdate = DateField()
    # P.9 Patient Gender
    sex = SetField(values=PATIENT_GENDERS)
    # P.14 Doctor
    physician_id = TextField()
    # P.26 Location. The general clinic location or nursing unit, or ward or
    # bed or both of the patient.
    location = TextField()


class OrderRecord(records.OrderRecord):
    """Order Record (O)

    Example:
    O|1|SID13|SID3^A123^5|^^^123^Assay1^UNDILUTED^P|R||20010223081223||||||||||||||||||F
    """
    # O.3 Specimen ID
    # Sample ID downloaded from Host, for Host-originated orders, or entered on
    # the system, for user-originated orders.
    sample_id = TextField()
    # O.4 Instrument Specimen ID
    instrument = ComponentField(
        Component.build(
            # O.4.1 Instrument Specimen ID
            TextField(name="specimen"),
            # O.4.2 Carrier/Carousel ID
            TextField(name="carrier"),
            # O.4.3 Position
            IntegerField(name="position"),
        ))
    # O.5 Universal Test ID
    test = ComponentField(
        Component.build(
            NotUsedField(name="_"),
            NotUsedField(name="__"),
            NotUsedField(name="___"),
            # O.5.4 Special number that identifies the test
            IntegerField(name="num"),
            # O.5.5 Assay test name
            TextField(name="name"),
            # 0.5.6 Dilution protocol name (empty for calculated results)
            TextField(name="dilution"),
            # 0.5.7 Assay status
            SetField(name="status", values=ASSAY_STATUSES),
        ))

    # O.6 Priority
    priority = SetField(values=PRIORITIES)
    # O.8 Date and time of sample collection
    sampled_at = DateTimeField()
    # O.12 Action Code. Q (Quality Control Result), Empty for Patient result
    action_code = TextField()
    # O.26 Report type
    report_type = SetField(values=REPORT_TYPES)


class CommentRecord(records.CommentRecord):
    """Comment Record (C)
    For test results, a comment record follows the final result record if
    information is entered in the comment field of the patient or QC order or
    result, or downloaded from the Host. For test exceptions, a comment record
    follows the order record and contain the reason for the test exception.

    Examples:
        C|1|I|Example Result Comment|G
    """
    # C.3 Comment Source
    source = ConstantField(default="I")
    # C.4 Result comment or exception string
    data = TextField()
    # C.5. Comment Type
    ctype = SetField(values=COMMENT_TYPES)


class ResultRecord(records.ResultRecord):
    """Record to transmit analytical data.

    Examples:
    R|1|^^^0021^B-hCG^UNDILUTED^P^47331M100^00788^^F|< 1.20|mIU/mL|0.35 TO 4.94|EXP^<||F||||19990715081030|I20100
    R|2|^^^0021^B-hCG^UNDILUTED^P^47331M100^00788^^I|NEGATIVE|||||F||||19990715081030|I20100
    R|3|^^^0021^B-hCG^UNDILUTED^P^47331M100^00788^^P|9245|RLU||||F||||19990715081030|I20100
    R|1|^^^0241^TSH^UNDILUTED^P^0607M200^01824^40080^F|4.6011|mIU/mL|4.292500 TO 5.397300|||F||ECB^RY||19990715081030|I20100
    """
    # R.3 Universal Test ID
    test = ComponentField(
        Component.build(
            NotUsedField("_"),
            NotUsedField("__"),
            NotUsedField("___"),
            # R.3.4 Specific number that identified the test
            IntegerField("num"),
            # R.3.5 Test name
            TextField("name"),
            # R.3.6 Dilution protocol name (empty for calculated test results)
            TextField("dilution"),
            # R.3.7 Status
            SetField(name="status", values=ASSAY_STATUSES),
            # R.3.8 Reagent Master Lot # (empty for calculated results)
            TextField("reagent_lot"),
            # R.3.9 Serial number of the reagent kit (empty for calculated)
            TextField("reagent_serial"),
            # R.3.10 Lot number of the control material (empty for patient
            # results and calculated results)
            TextField("control_lot"),
            # R.3.11 Result type
            SetField(name="result_type", values=RESULT_TYPES)
        )
    )
    # R.4 Data Value
    # For Result Type F (concentration value if within dynamic range -- may
    # include > or <). For Result Type P (numeric instrument response). For
    # Result Type I (interpretation)
    value = TextField()
    # R.5 Units
    # For Result Type F, result units. For Result Type P (RLU, Abs, or mV).
    # Empty for Result Type I
    units = TextField()
    # R.6 Result ranges
    # - For Result Type F for Patient Result: Normal/Therapeutic Ranges
    # - For Result Type F for Control Result: Control Range
    # - For Result Type I or P and for Result Type F, if range undefined: empty
    references = TextField()
    # R.7.1 Abnormal flags
    # For Result Type F: This field can be blank or contain one of the
    # following flags: LOW, HIGH, LL, HH, <, >, or EDIT, EXP, EXPC, CNTL,
    # Westgard Flags, A#1, A#2, CORR, FLEX, PSHH, IUO, INDX (post launch).
    # For Result Type P and I: This field is blank.
    #
    # NOTE: Multiple flags can be sent when the Result Type in field 10.1.3 is
    # F. Multiple flags are sent separated by component delimiters (which are
    # used as a repeat delimiter).
    #
    # The following flags are Westgard analysis flags and only display if the
    # result is a control: 1-2s, 1-3s, 2-2s1R1M, 2-2s1RxM, 2-2sxR1M, R-4s,
    # 4-1s1M, 4-1sxM, 10-x1M, 10-xxM
    abnormal_flag = RepeatedComponentField(
        Component.build(
            TextField(name="flag")
        ))
    # R.9 Result Status
    status = SetField(values=RESULT_STATUSES)
    # R.11 Operator Identification
    operator = ComponentField(
        Component.build(
            # R.11.1 ID of Operator logged into system at time of order
            TextField("order_operator"),
            # R.11.2 ID of Operator logged in at time of result release
            TextField("release_operator"),
        ))
    # R.13: Date and time the test processing completed
    completed_at = DateTimeField()
    # R.14: Instrument Identification
    # Serial # of the module which performed the test. Module serial
    # number for all tests except calculated test results, which returns the
    # system serial number
    instrument = TextField()


class RequestInformationRecord(records.RequestInformationRecord):
    """Request information Record (Q)
    """


class ManufacturerInfoRecord(records.ManufacturerInfoRecord):
    """Manufacturer Specific Records (M)
    """


class TerminatorRecord(records.TerminatorRecord):
    """Message Termination Record (L)
    """
