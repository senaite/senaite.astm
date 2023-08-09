# -*- coding: utf-8 -*-

from senaite.astm import records
from senaite.astm.fields import ComponentField
from senaite.astm.fields import ConstantField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import SetField
from senaite.astm.fields import IntegerField
from senaite.astm.fields import DecimalField
from senaite.astm.fields import TextField
from senaite.astm.fields import NotUsedField
from senaite.astm.mapping import Component


def get_wrappers():
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

    This record must always be the first record in a transmission. This record
    contains information about the sender and receiver, instruments, and
    computer system whose records are being exchanged. It also identifies the
    delimiter characters. The minimum information that must be sent in a Header
    record is: H|\^&{RT}

    Example:
    H|\^&|||c111^Roche^c111^0.5.4.0509^1^1005|||||host|RSUPL^BATCH|P|1|200 51021152259{RT}
    """
    sender = ComponentField(
        Component.build(
            TextField(name="name"),
            ConstantField(name="manufacturer", default="Roche"),
            ConstantField(name="instrument_type", default="c111"),
            TextField(name="version"),
            TextField(name="protocol_version"),
            TextField(name="serial_number"),
        ))

    comments = ComponentField(
        Component.build(
            TextField(name="message_purpose"),
            TextField(name="message_cause"),
        )
    )
    processing_id = ConstantField(default="P")
    receiver = TextField()
    version = TextField()


class PatientRecord(records.PatientRecord):
    """Patient Information Record (P)

    This record is used to transfer patient information to the analyzer (test
    order messages) or to the host (result messages).

    Example:
    P|1||[SampleIDpart]
    """


class OrderRecord(records.OrderRecord):

    # 9.4.3: Speciment ID
    #        -> only used when cobas 111 *receives* data
    sample_id = ComponentField(
        Component.build(
            TextField(name="sample_id"),
            TextField(name="rack_id"),
            TextField(name="rack_position"),
        )
    )

    # 9.4.4: Instrument Speciment ID
    #        -> only used when cobas 111 *transmits* data
    instrument = ComponentField(
        Component.build(
            TextField(name="sample_id"),
            TextField(name="rack_id"),
            TextField(name="rack_pos"),
            TextField(name="tray_id"),
            TextField(name="rack_type"),
            TextField(name="control_type"),
        )
    )

    # 9.4.6: Priority
    priority = SetField(values=["R", "S"])

    # 9.4.23: Date/Time Reported
    modified_at = DateTimeField()


class CommentRecord(records.CommentRecord):
    """Comment Record (C)
    """


class ResultRecord(records.ResultRecord):
    """Record to transmit analytical data.

    Example:
    4R|1|^^^687|49.2|U/L|20.0\30.0|H||F||admin
    """

    # 10.1.3: Universal Test ID
    #         Example: ^^^103^D
    test = ComponentField(
        Component.build(
            NotUsedField(name="_"),
            NotUsedField(name="__"),
            NotUsedField(name="___"),
            TextField(name="test_id"),
            # Specifies treatment to be done on instrument: (A)utodilution,
            # (D)ilution and factor, (C)oncentration and factor, etc., e.g. A,
            # D100, etc.
            TextField(name="treatment"),
            TextField(name="pre_treatment"),
            TextField(name="result_evaluation"),
        )
    )

    # 10.1.4: Data or Measurement Value
    value = TextField()

    # 10.1.5: Units
    #         Example: mg/dL
    units = TextField()

    # 10.1.06: Reference Ranges
    references = TextField()

    # 10.1.07: Result Abnormal Flags
    abnormal_flag = SetField(values=["L", "H", "<", ">", "N", "A"])

    # 10.1.09: Result Status
    status = SetField(values=["F", "C", "X", "R", "I"])

    # 10.1.11: Operator Identification
    operator = TextField()

    # 10.1.12: Date time test started
    started_at = DateTimeField()

    # 10.1.13: Date time test completed
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
