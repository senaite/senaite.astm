# -*- coding: utf-8 -*-

from senaite.astm import records
from senaite.astm.fields import ComponentField
from senaite.astm.fields import DateField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import JSONListField
from senaite.astm.fields import NotUsedField
from senaite.astm.fields import SetField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component

VERSION = "1.0.0"
HEADER_RX = r".*(?<=\|)(LIS|ABX)(?=\|).*"


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

    # Note: Although the field comes in as a single value text, we need to nest
    #       it for senaite.core.astm.consumer.get_sender_name to work properly
    sender = ComponentField(
        Component.build(
            TextField(name="name"),
        ))

    processing_id = SetField(
        field=TextField(),
        # P: Patient message, Q: Quality control message, D: Technician
        values=("P", "Q", "D"))

    version = TextField()


class PatientRecord(records.PatientRecord):
    """Patient Information Record (P)
    """

    # Patient Id (Advised on ABX Pentra XL80 for workflow management)
    laboratory_id = TextField(length=25)

    # format: Name^First name
    name = ComponentField(
        Component.build(
            TextField(name="name"),
            TextField(name="first_name"),
        ))

    # format: YYYYMMDD
    birthdate = DateField()

    # M, F or U
    sex = SetField(
        field=TextField(),
        length=1,
        values=("M", "F", "U"))


class OrderRecord(records.OrderRecord):
    """Order Record (O)
    """

    # Note: Field 9.4.3 "Sample ID" for ABX Pentra XL80 and Pentra XLR (Only
    # from Instrument to Host) is presented as follows:
    # SampleID^Rack(2 digits max.)^TubePosition(2 digits max.), e.g.
    # 45264012^02^08
    sample_id = ComponentField(
        Component.build(
            TextField(name="sample_id"),
            TextField(name="rack"),
            TextField(name="position"),
        )
    )

    # Note: Field 9.4.5 "Universal test ID" must be filled by the parameters
    # panel requested (CBC or DIF or RET or DIR or CBR):
    # Refer to Special characteristics for HORIBA Medical data on page 16.).
    test = ComponentField(
        Component.build(
            NotUsedField(name="_"),
            NotUsedField(name="__"),
            NotUsedField(name="___"),
            SetField(
                name="testname",
                field=TextField(),
                values=("CBC", "DIF", "RET", "DIR", "CBR")),
        ))

    # format: YYYYMMDDHHMMSS
    sampled_at = DateTimeField()

    # format: YYYYMMDDHHMMSS
    collected_at = DateTimeField()

    biomaterial = TextField()
    report_type = SetField(
        field=TextField(),
        length=1,
        values=("F", "C"))  # F: final; C: correction


class CommentRecord(records.CommentRecord):
    """Comment Record (C)
    """
    # I: clinical instrument system
    source = SetField(
        field=TextField(),
        length=1,
        values=("I"))

    # Text (Refer to Table 23 - Analytical alarms, page 18; Table 24 - Analyzer
    # alarms, page 18; Table 25 - Suspected pathologies, page 18.
    #
    # Note: values come in either as a string or a list with variable length.
    #       Therefore, we simply handle it as a JSON list
    data = JSONListField()

    # G:Free text
    # I: Instrument flag comment
    # L: Comment from host (Patient order) P80 V1.1 and above
    ctype = SetField(
        field=TextField(),
        length=1,
        values=("G", "I", "L"))


class ResultRecord(records.ResultRecord):
    """Record to transmit analytical data.
    """

    # Note: Field 10.1.3 "Universal TestID" for ABX Pentra XL80 and Pentra XLR
    # includes the dilution ratio as follows: ^^^Result name in english^LOINC
    # code^CDR (CDR=1 or 2 or 3 or 5). Results are returned in between ().
    test = ComponentField(
        Component.build(
            NotUsedField(name='_'),
            NotUsedField(name='__'),
            NotUsedField(name='___'),
            TextField(name='result_name'),
            TextField(name='loinc_code'),
            SetField(
                name="testname",
                field=TextField(),
                values=("1", "2", "3", "5")),
        ))

    value = TextField()

    units = SetField(
        field=TextField(),
        length=1,
        values=("1", "2", "3", "4"))

    abnormal_flag = SetField(
        field=TextField(),
        length=2,
        values=("L", "H", "LL", "HH", ">"))

    # W: suspicion
    # N: rejected result
    # F: final result
    # X: Parameter exceeding the capacity
    #    (ABX Pentra 80 / ABX Pentra XL80 / Pentra XLR)
    # M: Value input manually (ABX Pentra XL80 / Pentra XLR)
    # D: Value obtained by dilution (ABX Pentra XL80 / Pentra XLR)
    status = SetField(
        field=TextField(),
        length=1,
        values=("W", "N", "F", "X", "M", "D"))

    # Operator Code + Name
    operator = TextField()

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
