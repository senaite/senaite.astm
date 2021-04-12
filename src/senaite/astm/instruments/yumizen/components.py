# -*- coding: utf-8 -*-

from senaite.astm.fields import NotUsedField
from senaite.astm.fields import DateField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component


# Patient Name
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

# Data structure.
Data = Component.build(
    TextField(name='encode', default='FLOATLE-stream/deflate:base64'),
    TextField(name='data', default='')
)

# Test structure.
UniversalTestID = Component.build(
    NotUsedField(name='_'),
    NotUsedField(name='__'),
    NotUsedField(name='___'),
    TextField(name='result_name'),
    TextField(name='assay_code', required=True),
    TextField(name='dilution'),
)

ReferenceRanges = Component.build(
    TextField(name='range'),
    TextField(name='range_name'),
)
