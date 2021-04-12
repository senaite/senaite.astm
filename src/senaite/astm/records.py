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

# flake8: noqa: E501

# Message Header Record
#
# | ASTM # | ASTM Name                       | Python Alias          |
# |--------+---------------------------------+-----------------------|
# |    6.1 | Record Type ID                  | Record Type           |
# |    6.2 | Delimiter Definition            | DelimiterDefinition   |
# |    6.3 | Message Control ID              | MessageControlID      |
# |    6.4 | Access Password                 | AccessPassword        |
# |    6.5 | Sender Namer or ID              | SenderName            |
# |    6.6 | Sender Street Address           | SenderStreetAddress   |
# |    6.7 | Reserved Field                  | ReservedField         |
# |    6.8 | Sender Telephone Number         | SenderTelephoneNumber |
# |    6.9 | Characteristics of Sender       | SenderCharacteristics |
# |   6.10 | Receiver ID                     | ReceiverID            |
# |   6.11 | Comment or Special Instructions | Comment               |
# |   6.12 | Processing ID                   | ProcessingID          |
# |   6.13 | Version Number                  | VersionNumber         |
# |   6.14 | Date and Time of Message        | DateTime              |
#
HeaderRecord = Record.build(
    ConstantField(name='RecordType', default='H'),
    RepeatedComponentField(Component.build(
        ConstantField(name='_', default=''),
        TextField(name='__')
    ), name='DelimiterDefinition', default=[[], ['', '&']]),
    # ^^^ workaround to define field:
    # ConstantField(name='delimeter', default='\^&'),
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


# Message Patient Record
#
# | ASTM # | ASTM Name                                             | Python Alias                    |
# |--------+-------------------------------------------------------+---------------------------------|
# |    7.1 | Record Type                                           | RecordType                      |
# |    7.2 | Sequence Number                                       | SequenceNumber                  |
# |    7.3 | Practice-Assigned Patient ID                          | PracticeAssignedPatientID       |
# |    7.4 | Laboratory-Assigned Patient ID                        | LaboratoryAssignedPatientID     |
# |    7.5 | Patient ID Number 3                                   | PatientIDNo3                    |
# |    7.6 | Patient Name                                          | Name                            |
# |    7.7 | Mother’s Maiden Name                                  | MothersMaidenName               |
# |    7.8 | Birthdate                                             | BirthDate                       |
# |    7.9 | Patient Sex                                           | Sex                             |
# |   7.10 | Patient Race-Ethnic Origin                            | RaceEthnicOrigin                |
# |   7.11 | Patient Address                                       | Address                         |
# |   7.12 | Reserved Field                                        | ReservedField                   |
# |   7.13 | Patient Telephone Number                              | TelephoneNumber                 |
# |   7.14 | Attending Physician ID                                | AttendingPhysicianID            |
# |   7.15 | Special Field 1                                       | SpecialField1                   |
# |   7.16 | Special Field 2                                       | SpecialField2                   |
# |   7.17 | Patient Height                                        | Height                          |
# |   7.18 | Patient Weight                                        | Weight                          |
# |   7.19 | Patient’s Known or Suspected Diagnosis                | KnownDiagnosis                  |
# |   7.20 | Patient Active Medications                            | ActiveMedications               |
# |   7.21 | Patient’s Diet                                        | Diet                            |
# |   7.22 | Practice Field Number 1                               | PracticeFieldNumber1            |
# |   7.23 | Practice Field Number 2                               | PracticeFieldNumber2            |
# |   7.24 | Admission and Discharge Dates                         | AdmissionDischargeDates         |
# |   7.25 | Admission Status                                      | AdmissionStatus                 |
# |   7.26 | Location                                              | Location                        |
# |   7.27 | Nature of Alternative Diagnostic Code and Classifiers | NatureAlternativeDiagnosticCode |
# |   7.28 | Alternative Diagnostic Code and Classification        | AlternativeDiagnosticCode       |
# |   7.29 | Patient Religion                                      | Religion                        |
# |   7.30 | Marital Status                                        | MaritalStatus                   |
# |   7.31 | Isolation Status                                      | IsolationStatus                 |
# |   7.32 | Language                                              | Language                        |
# |   7.33 | Hospital Service                                      | HospitalService                 |
# |   7.34 | Hospital Institution                                  | HospitalInstitution             |
# |   7.35 | Dosage Category                                       | DosageCategory                  |
#
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


#: +-----+--------------+--------------------------------+--------------------+
#: |  #  | ASTM Field # | ASTM Name                      | Python alias       |
#: +=====+==============+================================+====================+
#: |   1 |        9.4.1 |                 Record Type ID |               type |
#: +-----+--------------+--------------------------------+--------------------+
#: |   2 |        9.4.2 |                Sequence Number |                seq |
#: +-----+--------------+--------------------------------+--------------------+
#: |   3 |        9.4.3 |                    Specimen ID |          sample_id |
#: +-----+--------------+--------------------------------+--------------------+
#: |   4 |        9.4.4 |         Instrument Specimen ID |         instrument |
#: +-----+--------------+--------------------------------+--------------------+
#: |   5 |        9.4.5 |              Universal Test ID |               test |
#: +-----+--------------+--------------------------------+--------------------+
#: |   6 |        9.4.6 |                       Priority |           priority |
#: +-----+--------------+--------------------------------+--------------------+
#: |   7 |        9.4.7 |    Requested/Ordered Date/Time |         created_at |
#: +-----+--------------+--------------------------------+--------------------+
#: |   8 |        9.4.8 |  Specimen Collection Date/Time |         sampled_at |
#: +-----+--------------+--------------------------------+--------------------+
#: |   9 |        9.4.9 |            Collection End Time |       collected_at |
#: +-----+--------------+--------------------------------+--------------------+
#: |  10 |       9.4.10 |              Collection Volume |             volume |
#: +-----+--------------+--------------------------------+--------------------+
#: |  11 |       9.4.11 |                   Collector ID |          collector |
#: +-----+--------------+--------------------------------+--------------------+
#: |  12 |       9.4.12 |                    Action Code |        action_code |
#: +-----+--------------+--------------------------------+--------------------+
#: |  13 |       9.4.13 |                    Danger Code |        danger_code |
#: +-----+--------------+--------------------------------+--------------------+
#: |  14 |       9.4.14 |           Relevant Information |      clinical_info |
#: +-----+--------------+--------------------------------+--------------------+
#: |  15 |       9.4.15 |    Date/Time Specimen Received |       delivered_at |
#: +-----+--------------+--------------------------------+--------------------+
#: |  16 |       9.4.16 |            Specimen Descriptor |        biomaterial |
#: +-----+--------------+--------------------------------+--------------------+
#: |  17 |       9.4.17 |             Ordering Physician |          physician |
#: +-----+--------------+--------------------------------+--------------------+
#: |  18 |       9.4.18 |        Physician’s Telephone # |    physician_phone |
#: +-----+--------------+--------------------------------+--------------------+
#: |  19 |       9.4.19 |               User Field No. 1 |       user_field_1 |
#: +-----+--------------+--------------------------------+--------------------+
#: |  20 |       9.4.20 |               User Field No. 2 |       user_field_2 |
#: +-----+--------------+--------------------------------+--------------------+
#: |  21 |       9.4.21 |         Laboratory Field No. 1 | laboratory_field_1 |
#: +-----+--------------+--------------------------------+--------------------+
#: |  22 |       9.4.22 |         Laboratory Field No. 2 | laboratory_field_2 |
#: +-----+--------------+--------------------------------+--------------------+
#: |  23 |       9.4.23 |             Date/Time Reported |        modified_at |
#: +-----+--------------+--------------------------------+--------------------+
#: |  24 |       9.4.24 |              Instrument Charge |  instrument_charge |
#: +-----+--------------+--------------------------------+--------------------+
#: |  25 |       9.4.25 |          Instrument Section ID | instrument_section |
#: +-----+--------------+--------------------------------+--------------------+
#: |  26 |       9.4.26 |                    Report Type |        report_type |
#: +-----+--------------+--------------------------------+--------------------+
#:
OrderRecord = Record.build(
    ConstantField(name='type', default='O'),
    IntegerField(name='seq', default=1, required=True),
    NotUsedField(name='sample_id'),
    NotUsedField(name='instrument'),
    NotUsedField(name='test'),
    NotUsedField(name='priority'),
    NotUsedField(name='created_at'),
    NotUsedField(name='sampled_at'),
    NotUsedField(name='collected_at'),
    NotUsedField(name='volume'),
    NotUsedField(name='collector'),
    NotUsedField(name='action_code'),
    NotUsedField(name='danger_code'),
    NotUsedField(name='clinical_info'),
    NotUsedField(name='delivered_at'),
    NotUsedField(name='biomaterial'),
    NotUsedField(name='physician'),
    NotUsedField(name='physician_phone'),
    NotUsedField(name='user_field_1'),
    NotUsedField(name='user_field_2'),
    NotUsedField(name='laboratory_field_1'),
    NotUsedField(name='laboratory_field_2'),
    NotUsedField(name='modified_at'),
    NotUsedField(name='instrument_charge'),
    NotUsedField(name='instrument_section'),
    NotUsedField(name='report_type'),
    NotUsedField(name='reserved'),
    NotUsedField(name='location_ward'),
    NotUsedField(name='infection_flag'),
    NotUsedField(name='specimen_service'),
    NotUsedField(name='laboratory')
)

#: +-----+--------------+--------------------------------+--------------------+
#: |  #  | ASTM Field # | ASTM Name                      | Python alias       |
#: +=====+==============+================================+====================+
#: |   1 |       10.1.1 |                 Record Type ID |               type |
#: +-----+--------------+--------------------------------+--------------------+
#: |   2 |       10.1.2 |                Sequence Number |                seq |
#: +-----+--------------+--------------------------------+--------------------+
#: |   3 |       10.1.3 |              Universal Test ID |               test |
#: +-----+--------------+--------------------------------+--------------------+
#: |   4 |       10.1.4 |      Data or Measurement Value |              value |
#: +-----+--------------+--------------------------------+--------------------+
#: |   5 |       10.1.5 |                          Units |              units |
#: +-----+--------------+--------------------------------+--------------------+
#: |   6 |       10.1.6 |               Reference Ranges |         references |
#: +-----+--------------+--------------------------------+--------------------+
#: |   7 |       10.1.7 |          Result Abnormal Flags |      abnormal_flag |
#: +-----+--------------+--------------------------------+--------------------+
#: |   8 |       10.1.8 |     Nature of Abnormal Testing | abnormality_nature |
#: +-----+--------------+--------------------------------+--------------------+
#: |   9 |       10.1.9 |                 Results Status |             status |
#: +-----+--------------+--------------------------------+--------------------+
#: |  10 |      10.1.10 | Date of Change in Instrument   |   norms_changed_at |
#: |     |              | Normative Values               |                    |
#: +-----+--------------+--------------------------------+--------------------+
#: |  11 |      10.1.11 |        Operator Identification |           operator |
#: +-----+--------------+--------------------------------+--------------------+
#: |  12 |      10.1.12 |         Date/Time Test Started |         started_at |
#: +-----+--------------+--------------------------------+--------------------+
#: |  13 |      10.1.13 |        Date/Time Test Complete |       completed_at |
#: +-----+--------------+--------------------------------+--------------------+
#: |  14 |      10.1.14 |      Instrument Identification |         instrument |
#: +-----+--------------+--------------------------------+--------------------+
#:
ResultRecord = Record.build(
    ConstantField(name='type', default='R'),
    IntegerField(name='seq', default=1, required=True),
    NotUsedField(name='test'),
    NotUsedField(name='value'),
    NotUsedField(name='units'),
    NotUsedField(name='references'),
    NotUsedField(name='abnormal_flag'),
    NotUsedField(name='abnormality_nature'),
    NotUsedField(name='status'),
    NotUsedField(name='norms_changed_at'),
    NotUsedField(name='operator'),
    NotUsedField(name='started_at'),
    NotUsedField(name='completed_at'),
    NotUsedField(name='instrument'),
)

#: +-----+--------------+---------------------------------+-------------------+
#: |  #  | ASTM Field # | ASTM Name                       | Python alias      |
#: +=====+==============+=================================+===================+
#: |   1 |       11.1.1 |                  Record Type ID |              type |
#: +-----+--------------+---------------------------------+-------------------+
#: |   2 |       11.1.2 |                 Sequence Number |               seq |
#: +-----+--------------+---------------------------------+-------------------+
#: |   3 |       11.1.3 |                  Comment Source |            source |
#: +-----+--------------+---------------------------------+-------------------+
#: |   4 |       11.1.4 |                    Comment Text |              data |
#: +-----+--------------+---------------------------------+-------------------+
#: |   5 |       11.1.5 |                    Comment Type |             ctype |
#: +-----+--------------+---------------------------------+-------------------+
#:
CommentRecord = Record.build(
    ConstantField(name='type', default='C'),
    IntegerField(name='seq', default=1, required=True),
    NotUsedField(name='source'),
    NotUsedField(name='data'),
    NotUsedField(name='ctype')
)

#: +-----+--------------+---------------------------------+-------------------+
#: |  #  | ASTM Field # | ASTM Name                       | Python alias      |
#: +=====+==============+=================================+===================+
#: |   1 |       13.1.1 |                  Record Type ID |              type |
#: +-----+--------------+---------------------------------+-------------------+
#: |   2 |       13.1.2 |                 Sequence Number |               seq |
#: +-----+--------------+---------------------------------+-------------------+
#: |   3 |       13.1.3 |                Termination code |              code |
#: +-----+--------------+---------------------------------+-------------------+
#:
TerminatorRecord = Record.build(
    ConstantField(name='type', default='L'),
    ConstantField(name='seq', default=1, field=IntegerField()),
    ConstantField(name='code', default='N')
)

#: +-----+--------------+---------------------------------+-------------------+
#: |  #  | ASTM Field # | ASTM Name                       | Python alias      |
#: +=====+==============+=================================+===================+
#: |   1 |       14.1.1 |                  Record Type ID |              type |
#: +-----+--------------+---------------------------------+-------------------+
#: |   2 |       14.1.2 |                 Sequence Number |               seq |
#: +-----+--------------+---------------------------------+-------------------+
#: |   3 |       14.1.3 |               Analytical Method |            method |
#: +-----+--------------+---------------------------------+-------------------+
#: |   4 |       14.1.4 |                 Instrumentation |        instrument |
#: +-----+--------------+---------------------------------+-------------------+
#: |   5 |       14.1.5 |                        Reagents |          reagents |
#: +-----+--------------+---------------------------------+-------------------+
#: |   6 |       14.1.6 |                Units of Measure |             units |
#: +-----+--------------+---------------------------------+-------------------+
#: |   7 |       14.1.7 |                 Quality Control |                qc |
#: +-----+--------------+---------------------------------+-------------------+
#: |   8 |       14.1.8 |             Specimen Descriptor |       biomaterial |
#: +-----+--------------+---------------------------------+-------------------+
#: |   9 |       14.1.9 |                  Reserved Field |          reserved |
#: +-----+--------------+---------------------------------+-------------------+
#: |  10 |      14.1.10 |                       Container |         container |
#: +-----+--------------+---------------------------------+-------------------+
#: |  11 |      14.1.11 |                     Specimen ID |         sample_id |
#: +-----+--------------+---------------------------------+-------------------+
#: |  12 |      14.1.12 |                         Analyte |           analyte |
#: +-----+--------------+---------------------------------+-------------------+
#: |  13 |      14.1.13 |                          Result |            result |
#: +-----+--------------+---------------------------------+-------------------+
#: |  14 |      14.1.14 |                    Result Units |      result_units |
#: +-----+--------------+---------------------------------+-------------------+
#: |  15 |      14.1.15 |        Collection Date and Time |        sampled_at |
#: +-----+--------------+---------------------------------+-------------------+
#: |  16 |      14.1.16 |            Result Date and Time |      completed_at |
#: +-----+--------------+---------------------------------+-------------------+
#: |  17 |      14.1.17 |  Analytical Preprocessing Steps |      preanalytics |
#: +-----+--------------+---------------------------------+-------------------+
#: |  18 |      14.1.18 |               Patient Diagnosis |         diagnosis |
#: +-----+--------------+---------------------------------+-------------------+
#: |  19 |      14.1.19 |               Patient Birthdate |         birthdate |
#: +-----+--------------+---------------------------------+-------------------+
#: |  20 |      14.1.20 |                     Patient Sex |               sex |
#: +-----+--------------+---------------------------------+-------------------+
#: |  21 |      14.1.21 |                    Patient Race |              race |
#: +-----+--------------+---------------------------------+-------------------+
#:
ScientificRecord = Record.build(
    ConstantField(name='type', default='S'),
    IntegerField(name='seq', default=1, required=True),
    NotUsedField(name='method'),
    NotUsedField(name='instrument'),
    NotUsedField(name='reagents'),
    NotUsedField(name='units'),
    NotUsedField(name='qc'),
    NotUsedField(name='biomaterial'),
    NotUsedField(name='reserved'),
    NotUsedField(name='container'),
    NotUsedField(name='sample_id'),
    NotUsedField(name='analyte'),
    NotUsedField(name='result'),
    NotUsedField(name='result_units'),
    NotUsedField(name='sampled_at'),
    NotUsedField(name='completed_at'),
    NotUsedField(name='preanalytics'),
    NotUsedField(name='diagnosis'),
    NotUsedField(name='birthdate'),
    NotUsedField(name='sex'),
    NotUsedField(name='race'),
)

#: +-----+--------------+---------------------------------+-------------------+
#: |  #  | ASTM Field # | ASTM Name                       | Python alias      |
#: +=====+==============+=================================+===================+
#: |   1 |       15.1.1 |                  Record Type ID |              type |
#: +-----+--------------+---------------------------------+-------------------+
#: |   2 |       15.1.2 |                 Sequence Number |               seq |
#: +-----+--------------+---------------------------------+-------------------+
#:
#: .. note::
#:   This record, which is similar to the comment record, may be used to send
#:   complex structures where use of the existing record types would not be
#:   appropriate. The fields within this record type are defined by the
#:   manufacturer.
#:
ManufacturerInfoRecord = Record.build(
    ConstantField(name='type', default='M'),
    IntegerField(name='seq', default=1, required=True),
)
