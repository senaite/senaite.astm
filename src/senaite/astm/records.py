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


__all__ = ['HeaderRecord', 'PatientRecord', 'OrderRecord',
           'ResultRecord', 'CommentRecord', 'TerminatorRecord']

# Message Header Record (See LIS2-A2 Section 6)
HeaderRecord = Record.build(
    ConstantField(name='RecordType', default='H'),
    RepeatedComponentField(Component.build(
        ConstantField(name='_', default=''),
        TextField(name='__')
    ), name='DelimiterDefinition', default=[[], ['', '&']]),
    # ^^^ workaround to define field:
    # ConstantField(name='DelimiterDefinition', default='\^&'),
    NotUsedField(name='MessageControlID'),
    NotUsedField(name='AccessPassword'),
    NotUsedField(name='SenderName'),
    NotUsedField(name='SenderStreetAddress'),
    NotUsedField(name='Reserved'),
    NotUsedField(name='SenderTelephoneNumber'),
    NotUsedField(name='SenderCharacteristics'),
    NotUsedField(name='ReceiverID'),
    NotUsedField(name='Comment'),
    ConstantField(name='ProcessingID', default='P'),
    NotUsedField(name='VersionNumber'),
    DateTimeField(name='DateTime', default=datetime.now, required=True),
)


# Message Patient Record (See LIS2-A2 Section 7)
PatientRecord = Record.build(
    ConstantField(name='RecordType', default='P'),
    IntegerField(name='SequenceNumber', default=1, required=True),
    NotUsedField(name='PracticeAssignedPatientID'),
    NotUsedField(name='LaboratoryAssignedPatientID'),
    NotUsedField(name='PatientIDNo3'),
    NotUsedField(name='Name'),
    NotUsedField(name='MothersMaidenName'),
    NotUsedField(name='BirthDate'),
    NotUsedField(name='Sex'),
    NotUsedField(name='RaceEthnicOrigin'),
    NotUsedField(name='Address'),
    NotUsedField(name='ReservedField'),
    NotUsedField(name='TelephoneNumber'),
    NotUsedField(name='AttendingPhysicianID'),
    NotUsedField(name='SpecialField1'),
    NotUsedField(name='SpecialField2'),
    NotUsedField(name='Height'),
    NotUsedField(name='Weight'),
    NotUsedField(name='KnownDiagnosis'),
    NotUsedField(name='ActiveMedications'),
    NotUsedField(name='Diet'),
    NotUsedField(name='PracticeFieldNumber1'),
    NotUsedField(name='PracticeFieldNumber2'),
    NotUsedField(name='AdmissionDischargeDates'),
    NotUsedField(name='AdmissionStatus'),
    NotUsedField(name='Location'),
    NotUsedField(name='NatureAlternativeDiagnosticCode'),
    NotUsedField(name='AlternativeDiagnosticCode'),
    NotUsedField(name='Religion'),
    NotUsedField(name='MaritalStatus'),
    NotUsedField(name='IsolationStatus'),
    NotUsedField(name='Language'),
    NotUsedField(name='HospitalService'),
    NotUsedField(name='HospitalInstitution'),
    NotUsedField(name='DosageCategory'),
)


# Test Order Record (See LIS2-A2 Section 8)
OrderRecord = Record.build(
    ConstantField(name='RecordType', default='O'),
    IntegerField(name='SequenceNumber', default=1, required=True),
    NotUsedField(name='SpecimenID'),
    NotUsedField(name='InstrumentSpecimenID'),
    NotUsedField(name='UniversalTestID'),
    NotUsedField(name='Priority'),
    NotUsedField(name='RequestedDate'),
    NotUsedField(name='CollectionDate'),
    NotUsedField(name='CollectionEndTime'),
    NotUsedField(name='CollectionVolume'),
    NotUsedField(name='CollectorID'),
    NotUsedField(name='ActionCode'),
    NotUsedField(name='DangerCode'),
    NotUsedField(name='RelevantClinicalInformation'),
    NotUsedField(name='DateSpecimenReceived'),
    NotUsedField(name='SpecimenDescriptor'),
    NotUsedField(name='OrderingPhysician'),
    NotUsedField(name='PhysicianTelephoneNumber'),
    NotUsedField(name='UserFieldNumber1'),
    NotUsedField(name='UserFieldNumber2'),
    NotUsedField(name='LaboratoryFieldNumber1'),
    NotUsedField(name='LaboratoryFieldNumber2'),
    NotUsedField(name='DateTimeResultsReported'),
    NotUsedField(name='InstrumentCharge'),
    NotUsedField(name='InstrumentCharge'),
    NotUsedField(name='ReportType'),
    NotUsedField(name='ReservedField'),
    NotUsedField(name='LocationSpecimenCollection'),
    NotUsedField(name='NosocomialInfectionFlag'),
    NotUsedField(name='SpecimenService'),
    NotUsedField(name='SpecimenInstitution')
)


# Result Record (See LIS2-A2 Section 9)
ResultRecord = Record.build(
    ConstantField(name='RecordType', default='R'),
    IntegerField(name='SequenceNumber', default=1, required=True),
    NotUsedField(name='UniversalTestID'),
    NotUsedField(name='Measurement'),
    NotUsedField(name='Units'),
    NotUsedField(name='ReferenceRanges'),
    NotUsedField(name='ResultAbnormalFlag'),
    NotUsedField(name='NatureOfAbnormality'),
    NotUsedField(name='ResultStatus'),
    NotUsedField(name='DateChange'),
    NotUsedField(name='OperatorIdentification'),
    NotUsedField(name='DateTimeStarted'),
    NotUsedField(name='DateTimeCompleted'),
    NotUsedField(name='InstrumentIdentification'),
)


# Comment Record (See LIS2-A2 Section 10)
CommentRecord = Record.build(
    ConstantField(name='RecordType', default='C'),
    IntegerField(name='SequenceNumber', default=1, required=True),
    NotUsedField(name='CommentSource'),
    NotUsedField(name='CommentText'),
    NotUsedField(name='CommentType')
)


# Request Information Record (See LIS2-A2 Section 11)
TerminatorRecord = Record.build(
    ConstantField(name='RecordType', default='Q'),
    ConstantField(name='SequenceNumber', default=1, field=IntegerField()),
    NotUsedField(name='StartingRangeIDNumber'),
    NotUsedField(name='EndingRangeIDNumber'),
    NotUsedField(name='UniversalTestID'),
    NotUsedField(name='NatureOfRequestTimeLimits'),
    NotUsedField(name='ResultsDateTimeBeginning'),
    NotUsedField(name='ResultsDateTimeEnding'),
    NotUsedField(name='PhysicianName'),
    NotUsedField(name='PhysicianTelephoneNumber'),
    NotUsedField(name='UserFieldNumber1'),
    NotUsedField(name='UserFieldNumber2'),
    NotUsedField(name='InformationStatusCodes'),
)


# Terminator Record (See LIS2-A2 Section 12)
TerminatorRecord = Record.build(
    ConstantField(name='RecordType', default='L'),
    ConstantField(name='SequenceNumber', default=1, field=IntegerField()),
    ConstantField(name='TerminationCode', default='N')
)


# Scientific Record (See LIS2-A2 Section 13)
ScientificRecord = Record.build(
    ConstantField(name='RecordType', default='S'),
    IntegerField(name='SequenceNumber', default=1, required=True),
    NotUsedField(name='AnalyticalMethod'),
    NotUsedField(name='Instrumentation'),
    NotUsedField(name='Reagents'),
    NotUsedField(name='Units'),
    NotUsedField(name='QualtityControl'),
    NotUsedField(name='SpecimentDescriptor'),
    NotUsedField(name='ReservedField'),
    NotUsedField(name='Container'),
    NotUsedField(name='SpecimentID'),
    NotUsedField(name='Analyte'),
    NotUsedField(name='Result'),
    NotUsedField(name='ResultUnits'),
    NotUsedField(name='CollectionDate'),
    NotUsedField(name='CollectionEndTime'),
    NotUsedField(name='AnalyticalPreprcessing'),
    NotUsedField(name='PatientDiagnosis'),
    NotUsedField(name='PatientBirthdate'),
    NotUsedField(name='PatientSex'),
    NotUsedField(name='PatientRace'),
)


# Manufacturer Record (See LIS2-A2 Section 14)
ManufacturerInfoRecord = Record.build(
    ConstantField(name='RecordType', default='M'),
    IntegerField(name='SequenceNumber', default=1, required=True),
)
