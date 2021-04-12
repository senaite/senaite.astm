# -*- coding: utf-8 -*-

from senaite.astm.fields import ComponentField
from senaite.astm.fields import NotUsedField
from senaite.astm.fields import ReadonlyField
from senaite.astm.fields import SetField
from senaite.astm.fields import DateField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component
from senaite.astm.records import CommentRecord
from senaite.astm.records import HeaderRecord
from senaite.astm.records import ManufacturerInfoRecord
from senaite.astm.records import OrderRecord
from senaite.astm.records import PatientRecord
from senaite.astm.records import ResultRecord
from senaite.astm.records import TerminatorRecord
from senaite.astm.wrapper import ASTMWrapper

#: Patient name structure.
PatientName = Component.build(
    TextField(name='Name', length=20),
    TextField(name='First Name', length=20)
)

# Patient Birthdate
PatientBirthDate = Component.build(
    DateField(name="birthdate"),
    TextField(name="age"),
    TextField(name="unit"),
)

#: Data structure.
Data = Component.build(
    TextField(name='encode', default='FLOATLE-stream/deflate:base64'),
    TextField(name='data', default='')
)

#: Test structure.
Test = Component.build(
    NotUsedField(name='_'),
    NotUsedField(name='__'),
    NotUsedField(name='___'),
    TextField(name='result_name'),
    TextField(name='assay_code', required=True),
    TextField(name='dilution'),
)

ReferenceRange = Component.build(
    TextField(name='range'),
    TextField(name='range_name'),
)


class Header(HeaderRecord):
    """ASTM header record.
    """


class Patient(PatientRecord):
    """ASTM patient record.
    """
    name = ComponentField(PatientName)
    birthdate = ComponentField(PatientBirthDate)
    sex = SetField(values=('M', 'F', None, 'U'))


class Order(OrderRecord):
    """ASTM order record.
    """


class Result(ResultRecord):
    """ASTM result record.
    """
    test = ComponentField(Test)
    value = TextField()
    units = TextField()
    references = ComponentField(ReferenceRange)
    abnormal_flag = SetField(
        field=TextField(),
        length=4,
        values=("HH", "H", "N", "L", "LL"))


class ManufacturerInfo(ManufacturerInfoRecord):
    """ManufacturerInfoRecord
    """
    message_type = SetField(
        name='message_type',
        values=('MATRIX', 'HISTOGRAM', 'REAGENT'))
    measurement_type = ReadonlyField(name='measurement_type')
    graphic_name = ReadonlyField(name='graphic_name')
    thresholds = ComponentField(Data)
    points = ComponentField(Data)


class Comment(CommentRecord):
    """ASTM comment record.
    """


class Terminator(TerminatorRecord):
    """ASTM terminator record.
    """


class H500(ASTMWrapper):
    """Yumizen H500
    """

    def __init__(self, *args, **kwargs):
        super(H500, self).__init__(*args, **kwargs)

        self.wrappers = {
            'H': Header,
            'P': Patient,
            'O': Order,
            'R': Result,
            'M': ManufacturerInfo,
            'C': Comment,
            'L': Terminator
        }

        self.json_format = {
            'P': {},
            'O': {},
            'M': [],
            'R': [],
        }

        self.skip_keys = ['type', 'seq']
