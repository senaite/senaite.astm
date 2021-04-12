# -*- coding: utf-8 -*-

from senaite.astm.fields import ComponentField
from senaite.astm.fields import ReadonlyField
from senaite.astm.fields import SetField
from senaite.astm.fields import TextField
from senaite.astm.records import CommentRecord
from senaite.astm.records import HeaderRecord
from senaite.astm.records import ManufacturerInfoRecord
from senaite.astm.records import OrderRecord
from senaite.astm.records import PatientRecord
from senaite.astm.records import ResultRecord
from senaite.astm.records import TerminatorRecord
from senaite.astm.wrapper import ASTMWrapper

from .components import Data
from .components import PatientBirthDate
from .components import PatientName
from .components import ReferenceRanges
from .components import UniversalTestID


class Header(HeaderRecord):
    """ASTM header record.
    """


class Patient(PatientRecord):
    """ASTM patient record.
    """
    Name = ComponentField(PatientName)
    Birthdate = ComponentField(PatientBirthDate)
    Sex = SetField(values=('M', 'F', 'U'))


class Order(OrderRecord):
    """ASTM order record.
    """


class Result(ResultRecord):
    """ASTM result record.

    See: 3.3.2.7. Result Record
    """
    UniversalTestID = ComponentField(UniversalTestID)
    Measurement = TextField()
    Units = TextField()
    ReferenceRanges = ComponentField(ReferenceRanges)
    ResultAbnormalFlag = SetField(
        field=TextField(),
        length=4,
        values=("HH", "H", "N", "L", "LL"))


class ManufacturerInfo(ManufacturerInfoRecord):
    """ManufacturerInfoRecord
    """
    MessageType = SetField(
        name='MessageType',
        values=('MATRIX', 'HISTOGRAM', 'REAGENT'))
    MeasurementType = ReadonlyField(name='MeasurementType')
    GraphicName = ReadonlyField(name='GraphicName')
    Thresholds = ComponentField(Data)
    Points = ComponentField(Data)


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
