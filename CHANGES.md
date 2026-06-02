# Changelog

## 2.0.0

- horiba_yumizen_h5xx: drop unused PatientRecord.unknown_1 / unknown_2 placeholders
- senaite-astm-send: auto-detect ASTM vs HL7 v2 inputs so HL7 captures can be replayed with the same CLI
- core: include CHANGES.md in setup.py long_description and add MANIFEST.in so the changelog ships in the sdist and renders on PyPI
- #64 core/lims: enforce a default HTTP timeout on Session.post / .get to prevent thread-pool starvation on a hung LIMS
- #66 admin: bound /stats request reads with a 5s timeout + 2 KiB cap and narrow except blocks to drop slowloris peers
- #67 senaite-astm-server: reject --capture-only combined with --url so a misconfigured systemd unit fails loudly
- #65 senaite-astm-send: switch --scrub-phi to a redact-by-allowlist policy so unknown P-record fields no longer leak
- #68 senaite-astm-server: wire AdminStats into ASTMProtocol and the frame callback so /stats reports real session and dispatch counts
- #69 core: bundled should-fix items — idempotent log handlers, sys.exit(1) on validate failure, --validate-only exit code capped, narrower transport / inspect except logging
- #63 senaite-astm-server: add --capture-only to persist captures without forwarding them to the LIMS
- #62 senaite-astm-server: add --admin-port for a read-only HTTP /stats endpoint (uptime, sessions, dispatches)
- #60 senaite-astm-inspect: new read-only CLI for instrument / summary / diff over captured ASTM files
- #59 senaite-astm-send: add --dry-run to log the planned request (URL, consumer, sizes) without contacting the LIMS
- #58 senaite-astm-send: add --filter-records / --drop-records to trim envelope buckets before serialisation
- #57 senaite-astm-send: add --scrub-phi to redact patient identifiers in the JSON envelope before pushing
- #56 senaite-astm-send: add --validate-only to parse + envelope-check captures without pushing to a LIMS
- #55 senaite-astm-send: add --substitute-sample-id OLD=NEW for retargeting a captured fixture without editing the file
- #54 senaite-astm-send: add -o / --output to convert captures to disk or stdout instead of pushing to a LIMS
- #53 senaite-astm-send: add --rebuild-checksums to repair hand-edited captures before parsing
- #52 senaite-astm-send: add -m / --message-format (json / astm / lis2a) for replaying captures into a LIMS
- #51 Decode Yumizen HISTOGRAM and MATRIX encoded streams into float lists in the envelope
- #50 Quiet empty-session disconnects: log TCP-probe drops at DEBUG, keep WARNING for mid-session cuts
- #49 Lift validate_lims, frame_callback dispatch, and LIMS arg group into _runtime
- #48 Synthetic ASTM adapters: extract framing dance into synthesize_session helper
- #47 HL7 parser: preserve unmapped segments under metadata.unmapped_segments
- #46 Pipeline: add optional dead_letter sink for failed handlers
- #45 lims.Session: drop unused **kw, return None from auth(), promote post_to_senaite kwargs
- #44 ASTMProtocol: rename discard_env to reset_session_state and prefer get_running_loop
- #43 Instrument base: provide a default get_metadata returning version + header_rx
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

## 1.0.0

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