# -*- coding: utf-8 -*-
"""Tests for :func:`senaite.astm.transports.hl7.parser.parse`.

The parser bridges the HL7-over-MLLP transport and the existing
typed :class:`Envelope` so downstream consumers see one schema
regardless of which transport the device speaks. The contract:

- MSH/PID/OBR/OBX/NTE land in the H/P/O/R/C buckets respectively.
- The raw HL7 text is preserved verbatim in ``metadata.hl7`` so disk
  capture and "push the original bytes" flows still work.
- ``metadata.astm`` and ``metadata.lis2a`` stay empty (HL7 envelopes
  have no native ASTM representation).
- The number of OBX entries matches the device's spec
  (exactly 20 for HemoScreen) and field indices map cleanly to the
  HL7 spec numbering.
- Optional NTE segments associated with flagged OBX entries appear
  in the C bucket.
- Malformed input raises ``ValueError`` rather than silently
  producing an empty envelope.
"""

import os
import unittest

from senaite.astm.core.envelope import (
    ENVELOPE_VERSION, Envelope, serialize_envelope,
)
from senaite.astm.transports.hl7.parser import parse


HERE = os.path.dirname(__file__)
FIXTURE_DIR = os.path.join(HERE, "data", "hl7")


def load_fixture(name):
    with open(os.path.join(FIXTURE_DIR, name), "rb") as fh:
        return fh.read()


class HemoScreenFreshBloodTest(unittest.TestCase):
    """Fixture: §8.1.1 fresh-blood ORU^R01."""

    @classmethod
    def setUpClass(cls):
        cls.envelope = parse(load_fixture("hemoscreen_fresh_blood.hl7"))

    def test_returns_envelope(self):
        self.assertIsInstance(self.envelope, Envelope)

    def test_envelope_version_is_current(self):
        self.assertEqual(
            self.envelope.metadata.envelope_version, ENVELOPE_VERSION)

    def test_header_bucket_has_sending_application(self):
        # MSH-3 == "HemoScreen", MSH-4 == "PixCell" — sender ID.
        self.assertEqual(len(self.envelope.H), 1)
        msh = self.envelope.H[0]
        self.assertEqual(msh["3"], "HemoScreen")
        self.assertEqual(msh["4"], "PixCell")
        self.assertEqual(msh["9"], "ORU^R01")
        self.assertEqual(msh["12"], "2.4")

    def test_patient_bucket_has_test_identifier(self):
        # PID-2 carries the HemoScreen Test Identifier (sample ID).
        self.assertEqual(len(self.envelope.P), 1)
        self.assertEqual(self.envelope.P[0]["2"], "35")

    def test_order_bucket_is_obs(self):
        self.assertEqual(len(self.envelope.O), 1)
        self.assertEqual(self.envelope.O[0]["4"], "OBS")

    def test_exactly_twenty_obx_results(self):
        self.assertEqual(len(self.envelope.R), 20)

    def test_first_obx_is_wbc(self):
        obx = self.envelope.R[0]
        self.assertEqual(obx["2"], "NM")
        self.assertEqual(obx["3"], "WBC")
        self.assertEqual(obx["5"], "11.7")
        self.assertEqual(obx["6"], "10*3/uL")
        self.assertEqual(obx["11"], "F")
        # OBX-15 is the device serial.
        self.assertEqual(obx["15"], "0000000-0001-HS")

    def test_no_nte_segments_for_unflagged_results(self):
        # OBS without flags must not carry NTE entries.
        self.assertEqual(len(self.envelope.C), 0)

    def test_metadata_hl7_preserves_raw_message(self):
        raw = self.envelope.metadata.hl7
        self.assertTrue(raw.startswith("MSH|^~\\&|HemoScreen|PixCell"))
        self.assertIn("OBX|0|NM|WBC", raw)

    def test_metadata_astm_and_lis2a_are_empty(self):
        self.assertEqual(self.envelope.metadata.astm, "")
        self.assertEqual(self.envelope.metadata.lis2a, "")


class HemoScreenQualityControlTest(unittest.TestCase):
    """Fixture: §8.1.2 LQC (Liquid Quality Control)."""

    @classmethod
    def setUpClass(cls):
        cls.envelope = parse(
            load_fixture("hemoscreen_quality_control.hl7"))

    def test_observation_type_is_lqc(self):
        self.assertEqual(self.envelope.O[0]["4"], "LQC")

    def test_patient_id_is_qc_lot_number(self):
        # QC vials carry a lot identifier in PID-2 — not a real
        # patient. The HemoScreen integration adapter (PR-8) is
        # responsible for routing this away from the LIMS push.
        self.assertEqual(self.envelope.P[0]["2"], "PIX240205N")

    def test_reference_ranges_present_for_lqc(self):
        # Per spec §5.1.5: reference ranges appear only on LQC.
        wbc = self.envelope.R[0]
        self.assertEqual(wbc["3"], "WBC")
        self.assertEqual(wbc["7"], "5.9-9.3")


class HemoScreenProficiencyTest(unittest.TestCase):
    """Fixture: §8.1.3 PRF (Proficiency / External Quality Control)."""

    @classmethod
    def setUpClass(cls):
        cls.envelope = parse(
            load_fixture("hemoscreen_proficiency.hl7"))

    def test_observation_type_is_prf(self):
        self.assertEqual(self.envelope.O[0]["4"], "PRF")

    def test_no_reference_ranges_for_prf(self):
        # Spec §5.1.5: ranges are PRF-suppressed.
        for obx in self.envelope.R:
            self.assertEqual(obx.get("7", ""), "")


class HemoScreenWithFlagsTest(unittest.TestCase):
    """Fixture: §8.1.4 flagged fresh-blood ORU^R01.

    Every OBX with a flag is followed by an NTE describing the flag;
    the parser must collect those into the C bucket.
    """

    @classmethod
    def setUpClass(cls):
        cls.envelope = parse(load_fixture("hemoscreen_with_flags.hl7"))

    def test_nte_count_matches_flagged_obx(self):
        # The fixture has 10 OBX entries with flags, each followed
        # by a matching NTE explaining the flag (NEU# / LYM# / MON# /
        # EOS# / BAS# / NEU% / LYM% / MON% / EOS% / BAS%).
        self.assertEqual(len(self.envelope.C), 10)

    def test_nte_carries_description(self):
        self.assertEqual(
            self.envelope.C[0]["3"],
            "Abnormal cells may affect marked results")

    def test_obx_with_LL_special_value(self):
        # OBX-2 == "ST" plus OBX-5 == "LL" signals below-linear.
        # Find the HGB result.
        hgb = next(obx for obx in self.envelope.R if obx["3"] == "HGB")
        self.assertEqual(hgb["2"], "ST")
        self.assertEqual(hgb["5"], "LL")

    def test_obx_with_triple_dash_special_value(self):
        mpv = next(obx for obx in self.envelope.R if obx["3"] == "MPV")
        self.assertEqual(mpv["5"], "---")

    def test_obx_flag_field_is_populated(self):
        # OBX-8 carries the flag symbol when present.
        neu = next(obx for obx in self.envelope.R if obx["3"] == "NEU#")
        self.assertEqual(neu["8"], "*")


class SerializerIntegrationTest(unittest.TestCase):
    """``serialize_envelope`` learns the ``"hl7"`` format in PR-7."""

    def test_serialize_returns_raw_payload(self):
        envelope = parse(load_fixture("hemoscreen_fresh_blood.hl7"))
        payload = serialize_envelope(envelope, "hl7")
        self.assertTrue(
            payload.startswith("MSH|^~\\&|HemoScreen|PixCell"))

    def test_serialize_json_includes_hl7_in_metadata(self):
        import json

        envelope = parse(load_fixture("hemoscreen_fresh_blood.hl7"))
        dumped = json.loads(serialize_envelope(envelope, "json"))
        self.assertIn("hl7", dumped["metadata"])
        self.assertEqual(dumped["metadata"]["astm"], "")
        self.assertEqual(dumped["metadata"]["lis2a"], "")


class ParserRobustnessTest(unittest.TestCase):

    def test_missing_msh_raises(self):
        with self.assertRaises(ValueError):
            parse(b"random garbage without HL7 structure")

    def test_accepts_bytes_and_str(self):
        raw = load_fixture("hemoscreen_fresh_blood.hl7")
        from_bytes = parse(raw)
        from_str = parse(raw.decode("utf-8"))
        # Bucket counts should match.
        self.assertEqual(len(from_bytes.R), len(from_str.R))

    def test_normalises_lf_to_cr(self):
        # Replace inter-segment terminators with \n; parser must
        # still produce a complete envelope.
        raw = load_fixture("hemoscreen_fresh_blood.hl7")
        lf_version = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        envelope = parse(lf_version)
        self.assertEqual(len(envelope.R), 20)

    def test_unknown_segments_are_preserved_in_metadata(self):
        # Inject a Z-segment (vendor-defined; not in SEGMENT_BUCKETS)
        # and an unknown ABC segment. Both must surface under
        # metadata.unmapped_segments instead of being dropped.
        raw = load_fixture("hemoscreen_fresh_blood.hl7").decode("utf-8")
        raw = raw.rstrip("\r") + "\rZDS|1|2|3\rABC|hello|world\r"
        envelope = parse(raw)
        extras = envelope.metadata.model_extra or {}
        unmapped = extras.get("unmapped_segments", {})
        self.assertIn("ZDS", unmapped)
        self.assertIn("ABC", unmapped)
        self.assertEqual(unmapped["ZDS"][0]["1"], "1")
        self.assertEqual(unmapped["ABC"][0]["2"], "world")

    def test_no_unmapped_segments_key_when_all_are_known(self):
        envelope = parse(load_fixture("hemoscreen_fresh_blood.hl7"))
        extras = envelope.metadata.model_extra or {}
        self.assertNotIn("unmapped_segments", extras)


if __name__ == "__main__":
    unittest.main()
