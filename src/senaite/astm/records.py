# -*- coding: utf-8 -*-

from datetime import datetime

from senaite.astm.fields import ConstantField
from senaite.astm.fields import DateTimeField
from senaite.astm.fields import IntegerField
from senaite.astm.fields import NotUsedField
from senaite.astm.fields import RepeatedComponentField
from senaite.astm.fields import TextField
from senaite.astm.mapping import Component
from senaite.astm.mapping import Record

HeaderRecord = Record.build(
    # ASTM 6.1: Record Type ID
    ConstantField(name='type', default='H'),
    # ASTM 6.2: Delimiter Definition
    # workaround for: ConstantField(name='delimeter', default='\^&')
    RepeatedComponentField(Component.build(
        ConstantField(name='_', default=''),
        TextField(name='__')
    ), name='delimeter', default=[[], ['', '&']]),
    # ASTM 6.3: Message Control ID
    NotUsedField(name='message_id'),
    # ASTM 6.4: Access Password
    NotUsedField(name='password'),
    # ASTM 6.5: Sender Name or ID (From device to host)
    NotUsedField(name='sender'),
    # ASTM 6.6: Sender Address
    NotUsedField(name='address'),
    # ASTM 6.7: Reserved Field
    NotUsedField(name='reserved'),
    # ASTM 6.8: Sender Telephone Nb
    NotUsedField(name='phone'),
    # ASTM 6.9: Characteristic of Sender
    NotUsedField(name='cos'),
    # ASTM 6.10: Receiver Name or ID (From Host to device)
    NotUsedField(name='receiver'),
    # ASTM 6.11: Comment or Special Instruction
    NotUsedField(name='comments'),
    # ASTM 6.12: Processing ID
    # « P » for a Patient analysis, « Q » for a QC, « D » for technician
    ConstantField(name='processing_id', default='P'),
    # ASTM 6.13: Version Number
    NotUsedField(name='version'),
    # ASTM 6.14: Date and Time of Message
    DateTimeField(name='timestamp', default=datetime.now, required=True),
)


PatientRecord = Record.build(
    # ASTM 7.1: Record Type ID
    ConstantField(name='type', default='P'),
    # ASTM 7.2: Sequence Number
    IntegerField(name='seq', default=1, required=True),
    # ASTM 7.3: Practice Assigned Patient ID
    NotUsedField(name='practice_id'),
    NotUsedField(name='laboratory_id'),
    NotUsedField(name='id'),
    NotUsedField(name='name'),
    NotUsedField(name='maiden_name'),
    NotUsedField(name='birthdate'),
    NotUsedField(name='sex'),
    NotUsedField(name='race'),
    NotUsedField(name='address'),
    NotUsedField(name='reserved'),
    NotUsedField(name='phone'),
    NotUsedField(name='physician_id'),
    NotUsedField(name='special_1'),
    NotUsedField(name='special_2'),
    NotUsedField(name='height'),
    NotUsedField(name='weight'),
    NotUsedField(name='diagnosis'),
    NotUsedField(name='medication'),
    NotUsedField(name='diet'),
    NotUsedField(name='practice_field_1'),
    NotUsedField(name='practice_field_2'),
    NotUsedField(name='admission_date'),
    NotUsedField(name='admission_status'),
    NotUsedField(name='location'),
    NotUsedField(name='diagnostic_code_nature'),
    NotUsedField(name='diagnostic_code'),
    NotUsedField(name='religion'),
    NotUsedField(name='martial_status'),
    NotUsedField(name='isolation_status'),
    NotUsedField(name='language'),
    NotUsedField(name='hospital_service'),
    NotUsedField(name='hospital_institution'),
    NotUsedField(name='dosage_category'),
)
