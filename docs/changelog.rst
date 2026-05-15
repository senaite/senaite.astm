Changelog
=========


1.0.0 (unreleased)
------------------

- #36 HL7-over-MLLP transport, passthrough only (PR-6 for the
  HemoScreen integration). Adds ``senaite-hl7-server`` (default
  port 2575) and ``senaite-hl7-simulator``. Captures each received
  HL7 v2 message to ``--output`` and responds with a comm-level
  ACK^R01. No parsing-to-envelope, no LIMS push (deferred to PR-7).
- #35 Disk capture is a first-class pipeline handler (PR-H).
  **Migration note:** the implicit ``$CWD/astm_messages/``
  directory is no longer auto-discovered. Pass ``--output <path>``
  explicitly to enable raw-message capture.
- #34 Server hardening: async main, sane log rotation, graceful
  shutdown of in-flight pipeline tasks (PR-G)
- #33 Split transport from protocol semantics (PR-F)
- #31 Migrate every instrument to the registry (PR-E2)
- #30 Introduce the instrument registry (PR-E1)
- #29 Make field descriptors quiet and tolerant (PR-D)
- #28 Define a typed Envelope schema for Wrapper.to_dict() (PR-C)
- #27 Lift LIMS push into core/ with typed errors and PushResult (PR-B)
- #26 Drop Python 2 compatibility shims (PR-A)
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
