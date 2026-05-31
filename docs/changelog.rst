Changelog
=========


2.0.0
-----

- #45 lims.Session: drop unused **kw, return None from auth(), promote post_to_senaite kwargs
- #42 Wrapper: drop duplicate get_mapping call and chain ValueError with 'from exc'
- #41 Document the HL7-over-MLLP transport and envelope bucket mapping
- #38 Use microsecond precision in capture filenames
- #37 HL7 v2 parser, envelope mapping, LIMS push wiring (PR-7)
- #36 HL7-over-MLLP transport, passthrough (PR-6, HemoScreen)
- #35 Disk capture is a first-class pipeline handler (PR-H)
- #34 Server hardening: async main, sane log rotation, graceful shutdown (PR-G)
- #33 Split transport from protocol semantics (PR-F)
- #31 Migrate every instrument to the registry (PR-E2)
- #30 Introduce the instrument registry (PR-E1)
- #29 Make field descriptors quiet and tolerant
- #28 Define a typed Envelope schema for Wrapper.to_dict()
- #27 Lift LIMS push into core/ with typed errors and PushResult
- #26 Drop Python 2 compatibility shims


1.0.0
-----

- #25 Add test scaffold for the ASTM pipeline
- #23 Add Cepheid GeneXpert import schema
- #22 Add Horiba Pentra XLR import schema
- #21 Add Biomérieux MINI VIDAS® import schema
- #20 Add Abbott Afinion™ 2 Analyzer import schema
- #19 Add Spotchem™EL SE-1520 import schema
- #18 Add Siemens' DCA Vantage® Analyzer import schema
- #17 Add Sysmex XP-100 import schema
- #16 Add Sysmex XN-550 import schema
- #15 Add Cobas C311 import schema
- #11 Fix same transport is used for different connections
- #9  Add Cobas C311 Test
- #7  Add Cobas C111 Test
- #6  Add Pentra XLR test
- #5  Allow to store the raw ASTM messages
- #4  Improve ASTM Protocol for Multi connections
- #3  Fix ASTM message splitting and added tests
- #1  Ensure output messages are LIS2-A2 compliant
