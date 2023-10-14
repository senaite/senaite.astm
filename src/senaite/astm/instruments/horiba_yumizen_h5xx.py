# -*- coding: utf-8 -*-

from senaite.astm import records
from senaite.astm.fields import ComponentField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import NotUsedField
from senaite.astm.fields import SetField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component

VERSION = "1.0.0"
# Supports H500 and H550
HEADER_RX = r".*H5[0,5]0\^"


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
    sample_id = TextField()
    instrument = TextField()
    test = ComponentField(
        Component.build(
            NotUsedField(name='_'),
            NotUsedField(name='__'),
            NotUsedField(name='___'),
            SetField(
                name='testname',
                field=TextField(),
                values=('CBC', 'DIF')),
        ))
    priority = ComponentField(
        Component.build(
            SetField(
                name='value',
                field=TextField(),
                values=('R', 'S')),
        ))
    requested_at = DateTimeField()
    received_at = DateTimeField()
    sampled_at = DateTimeField()
    reported_at = DateTimeField()


class CommentRecord(records.CommentRecord):
    """Comment Record (C)
    """


class ResultRecord(records.ResultRecord):
    """Record to transmit analytical data.
    """
    test = ComponentField(
        Component.build(
            NotUsedField(name='_'),
            NotUsedField(name='__'),
            NotUsedField(name='___'),
            TextField(name='result_name'),
            TextField(name='assay_code'),
            TextField(name='dilution'),
        ))
    value = TextField()
    units = TextField()
    references = ComponentField(
        Component.build(
            TextField(name='result_range'),
            TextField(name='range_name'),
        ))
    abnormal_flag = SetField(
        field=TextField(),
        length=4,
        values=("HH", "H", "N", "L", "LL"))
    status = SetField(
        field=TextField(),
        length=1,
        values=("W", "X", "F"))
    operator = ComponentField(
        Component.build(
            TextField(name='login'),
            NotUsedField(name='_'),
            TextField(name='profile'),
        ))
    started_at = DateTimeField()
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
