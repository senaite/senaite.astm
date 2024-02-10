# -*- coding: utf-8 -*-

from senaite.astm import records
from senaite.astm.fields import ComponentField
from senaite.astm.fields import ConstantField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import RepeatedComponentField
from senaite.astm.fields import SetField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component

VERSION = "1.0.0"
HEADER_RX = r".*c311\^"

ABNORMAL_FLAGS = ["L", "H", "LL", "HH", "N", "A",]
ACTION_CODES = ["N", "Q", "A", "C",]
CONTAINER_TYPES = ["SC", "MC",]
MSG_MEANINGS = ["TSREQ", "TSDWN", "RSUPL", "PCUPL", "ICUPL", "ABUPL", "RSREQ",]
MSG_MODES = ["REAL", "BATCH", "REPLY",]
PRIORITIES = ["R", "S",]
SAMPLE_TYPES = ["S1", "S2", "S3", "S4", "S5", "S0", "QC",]
STATUS = ["F", "C",]


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
            TextField(name="name", default="c311"),
            TextField(name="version"),
        ))

    comments = ComponentField(
        Component.build(
            SetField(name="meaning_of_message", values=MSG_MEANINGS),
            SetField(name="mode_of_message", values=MSG_MODES),
        )
    )
    processing_id = ConstantField(default="P")
    receiver = TextField()
    version = TextField()


class PatientRecord(records.PatientRecord):
    """Patient Information Record (P)
    """
    birthdate = DateTimeField()
    sex = TextField()
    special_1 = ComponentField(
        Component.build(
            TextField(name="age"),
            TextField(name="unit"),
        )
    )


class OrderRecord(records.OrderRecord):
    """Order Record (O)
    """

    # NOTE: This field behaves different thant described in the documentation!
    #       It should be a single string, but is a component of 5 fields
    sample_id = ComponentField(
        Component.build(
            TextField(name="sample_total_counter"),
            TextField(name="sample_id"),
            TextField(name="sample_count"),
            TextField(name="_"),
            TextField(name="sample_daily_counter"),
        )
    )

    # NOTE: This field behaves different thant described in the documentation!
    #       It should be a component field as described below, but is a single
    #       string field
    instrument = ComponentField(
        Component.build(
            TextField(name="sequence_number"),
            TextField(name="rack_id"),
            TextField(name="position_number"),
            SetField(name="sample_type", values=SAMPLE_TYPES),
            SetField(name="container_type", values=CONTAINER_TYPES),
        )
    )

    test = RepeatedComponentField(
        Component.build(
            TextField(name="_"),
            TextField(name="__"),
            TextField(name="___"),
            TextField(name="application_code"),
            TextField(name="dilution"),
        )
    )

    priority = SetField(values=PRIORITIES)
    sampled_at = DateTimeField()
    reported_at = DateTimeField()
    action_code = SetField(values=ACTION_CODES)
    biomaterial = TextField()
    report_type = TextField()


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
            TextField(name="application_code"),
            TextField(name="dilution"),
        )
    )

    value = TextField()
    units = TextField()
    abnormal_flag = SetField(values=ABNORMAL_FLAGS)
    status = SetField(values=STATUS)
    operator = TextField()
    started_at = DateTimeField()
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
