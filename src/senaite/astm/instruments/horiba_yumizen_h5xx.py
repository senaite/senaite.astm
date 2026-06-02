# -*- coding: utf-8 -*-

import re

from senaite.astm import records
from senaite.astm.core.instrument import Instrument
from senaite.astm.core.instrument import register_instrument
from senaite.astm.fields import ComponentField
from senaite.astm.fields import ConstantField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import EncodedStreamField
from senaite.astm.fields import IntegerField
from senaite.astm.fields import NotUsedField
from senaite.astm.fields import PassthroughField
from senaite.astm.fields import SetField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component
from senaite.astm.mapping import Record

VERSION = "1.0.0"
# Supports H500 and H550
HEADER_RX = re.compile(rb".*H5[0,5]0\^")


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


# The Yumizen overloads the M record across several row types
# (HISTOGRAM, MATRIX, REAGENT, ...). Each row looks like:
#
#   1M|1|HISTOGRAM|RBC/PLT|RbcAlongRes|FLOATLE-stream/...|FLOATLE-stream/...
#
# The slot semantics depend on the `kind` tag in M-3:
#
#   M-3 kind     M-4         M-5            M-6              M-7
#   ---------    --------    -----------    --------------   --------------
#   HISTOGRAM    domain      stream         axis_x (stream)  axis_y (stream)
#   MATRIX       domain      stream         axis_x (stream)  axis_y (stream)
#   REAGENT      list        repeated cmps  (unused)         (unused)
#
# `kind` is always a string tag. `domain` and `stream` may be plain
# strings, backslash-separated lists, or repeated components — so
# they use PassthroughField, which preserves the original shape.
# axis_x / axis_y are encoded streams for HISTOGRAM / MATRIX and
# something else for REAGENT; EncodedStreamField decodes only when
# the prefix matches and passes other values through.
#
# Rebuild rather than subclass: the base ManufacturerInfoRecord is
# all NotUsedField, which would discard everything we care about.
ManufacturerInfoRecord = Record.build(
    ConstantField(name="type", default="M"),
    IntegerField(name="seq", default=1, required=True),
    TextField(name="kind"),
    PassthroughField(name="domain"),
    PassthroughField(name="stream"),
    EncodedStreamField(name="axis_x"),
    EncodedStreamField(name="axis_y"),
)


class TerminatorRecord(records.TerminatorRecord):
    """Message Termination Record (L)
    """


@register_instrument
class HoribaYumizenH5xx(Instrument):
    name = "horiba_yumizen_h5xx"
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


INSTRUMENT = HoribaYumizenH5xx()
