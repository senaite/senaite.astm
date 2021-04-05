# -*- coding: utf-8 -*-

from datetime import datetime

from senaite.astm.fields import ConstantField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import NotUsedField
from senaite.astm.fields import RepeatedComponentField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component
from senaite.astm.mapping import Record


HeaderRecord = Record.build(
    # Record Type ID
    ConstantField(name='type', default='H'),

    RepeatedComponentField(Component.build(
        ConstantField(name='_', default=''),
        TextField(name='__')
    ), name='delimeter', default=[[], ['', '&']]),
    # ^^^ workaround to define field:
    # ConstantField(name='delimeter', default='\^&'),
)
