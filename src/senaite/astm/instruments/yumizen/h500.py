# -*- coding: utf-8 -*-

from senaite.astm.fields import ComponentField
from senaite.astm.fields import RawField
from senaite.astm.fields import SetField
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


#: Data structure.
#:
#: :param encode: data encoding
#: :type encode: str
#:
#: :param data: Base64 encoded data
#: :type first: str
#:
Data = Component.build(
    TextField(name='encode', default='FLOATLE-stream/deflate:base64'),
    TextField(name='data', default='')
)


class Header(HeaderRecord):
    """ASTM header record.
    """


class Patient(PatientRecord):
    """ASTM patient record.
    """


class Order(OrderRecord):
    """ASTM order record.
    """


class Result(ResultRecord):
    """ASTM result record.
    """


class ManufacturerInfo(ManufacturerInfoRecord):
    """ManufacturerInfoRecord
    """
    message_type = SetField(
        name='message_type',
        values=('MATRIX', 'HISTOGRAM', 'REAGENT'))
    measurement_type = RawField(name='measurement_type')
    graphic_name = RawField(name='graphic_name')
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
