# -*- coding: utf-8 -*-

from senaite.astm.records import CommentRecord
from senaite.astm.records import HeaderRecord
from senaite.astm.records import OrderRecord
from senaite.astm.records import PatientRecord
from senaite.astm.records import ResultRecord
from senaite.astm.records import TerminatorRecord
from senaite.astm.records import ManufacturerInfoRecord
from senaite.astm.wrapper import ASTMWrapper


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
