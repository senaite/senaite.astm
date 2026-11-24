# -*- coding: utf-8 -*-
"""Tests for `senaite-astm-send --scrub-phi`.

The flag redacts patient-identifying fields in the typed envelope
before serialisation so real captures can be replayed against a
dev / staging LIMS without leaking PHI. The policy is redact-by-
allowlist: everything in a P record is scrubbed unless its key is
in :data:`PHI_NON_PHI_KEYS`. Only the JSON output is scrubbed; raw
ASTM / LIS2-A bytes are intentionally cleared so a downstream
consumer can't pull them back to the unredacted form.
"""

import json
import os
import unittest

from senaite.astm.core.envelope import Envelope
from senaite.astm.core.envelope import Metadata
from senaite.astm.sender import PHI_NON_PHI_KEYS
from senaite.astm.sender import PHI_REDACTION
from senaite.astm.sender import _file_to_message
from senaite.astm.sender import _scrub_envelope_phi


HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "data")
FIXTURE = os.path.join(DATA_DIR, "yumizen_h500.txt")


def _envelope(scrub=False, phi_keep=()):
    msg = _file_to_message(
        open(FIXTURE, "rb"), "json",
        scrub_phi=scrub, phi_keep=phi_keep)
    return json.loads(msg)


def _full_patient():
    """Build a P record populated across the full ASTM PatientRecord
    schema so a scrub call exercises every field. Every value is a
    truthy string so the truthy-check in the scrubber does not skip
    any field accidentally."""
    return {
        "type": "P",
        "seq": "1",
        # ASTM PatientRecord fields (senaite.astm.records)
        "practice_id": "PRX-001",
        "laboratory_id": "LAB-002",
        "id": "MRN-003",
        "name": "Doe^John^A",
        "maiden_name": "Smith",
        "birthdate": "19800101",
        "sex": "M",
        "race": "human",
        "address": "1 Main St",
        "reserved": "rsv",
        "phone": "+1234567890",
        "physician_id": "DR-004",
        "special_1": "free text",
        "special_2": "free text 2",
        "height": "180",
        "weight": "75",
        "diagnosis": "free text diagnosis",
        "medication": "free text medication",
        "diet": "free text diet",
        "practice_field_1": "lab tag a",
        "practice_field_2": "lab tag b",
        "admission_date": "20260101",
        "admission_status": "INP",
        "location": "Ward 5",
        "diagnostic_code_nature": "ICD10",
        "diagnostic_code": "Z00.0",
        "religion": "n/a",
        "martial_status": "S",
        "isolation_status": "none",
        "language": "EN",
        "hospital_service": "Hematology",
        "hospital_institution": "General Hospital",
        "dosage_category": "STD",
    }


class ScrubPhiPolicyTest(unittest.TestCase):
    """Allowlist policy: everything outside PHI_NON_PHI_KEYS is
    redacted; everything inside passes through verbatim."""

    def test_every_pii_field_is_redacted(self):
        env = Envelope(metadata=Metadata())
        env.P.append(_full_patient())
        _scrub_envelope_phi(env)
        patient = env.P[0]
        for key, value in patient.items():
            if key in PHI_NON_PHI_KEYS:
                continue
            self.assertEqual(
                value, PHI_REDACTION,
                "%s leaked: %r" % (key, value))

    def test_allowlisted_fields_pass_through(self):
        env = Envelope(metadata=Metadata())
        original = _full_patient()
        env.P.append(dict(original))
        _scrub_envelope_phi(env)
        patient = env.P[0]
        for key in PHI_NON_PHI_KEYS:
            if key in original:
                self.assertEqual(
                    patient[key], original[key],
                    "%s was wrongly redacted" % key)

    def test_phi_keep_extends_the_allowlist(self):
        env = Envelope(metadata=Metadata())
        env.P.append({
            "type": "P",
            "seq": "1",
            "name": "Doe^John",
            "vendor_tag": "non-identifying-value",
        })
        _scrub_envelope_phi(env, keep_keys=("vendor_tag",))
        self.assertEqual(env.P[0]["name"], PHI_REDACTION)
        self.assertEqual(env.P[0]["vendor_tag"],
                         "non-identifying-value")

    def test_known_blocklist_regression(self):
        """The original hand-picked blocklist missed these keys —
        the allowlist policy must cover all of them."""
        env = Envelope(metadata=Metadata())
        env.P.append({
            "type": "P",
            "seq": "1",
            "practice_id": "PR-1",
            "laboratory_id": "LAB-1",
            "admission_date": "20260101",
            "diagnostic_code": "Z00.0",
            "hospital_institution": "General Hospital",
            "hospital_service": "Hematology",
            "location": "Ward 5",
            "special_1": "free text",
            "special_2": "free text 2",
            "practice_field_1": "tag a",
            "practice_field_2": "tag b",
            "religion": "n/a",
            "language": "EN",
        })
        _scrub_envelope_phi(env)
        for key in (
            "practice_id", "laboratory_id", "admission_date",
            "diagnostic_code", "hospital_institution",
            "hospital_service", "location",
            "special_1", "special_2",
            "practice_field_1", "practice_field_2",
            "religion", "language",
        ):
            self.assertEqual(
                env.P[0][key], PHI_REDACTION,
                "%s leaked: %r" % (key, env.P[0][key]))


class ScrubPhiMetadataTest(unittest.TestCase):

    def test_metadata_raw_payloads_are_cleared(self):
        env = _envelope(scrub=True)
        # Both flat-text payloads carry the verbatim records and
        # would re-leak the patient name; the scrubber clears them.
        self.assertEqual(env["metadata"].get("astm", ""), "")
        self.assertEqual(env["metadata"].get("lis2a", ""), "")

    def test_metadata_payloads_present_without_scrub(self):
        env = _envelope(scrub=False)
        # Sanity: at least one of the flat payloads is populated
        # in the unscrubbed envelope.
        self.assertTrue(
            env["metadata"].get("astm")
            or env["metadata"].get("lis2a"))


class ScrubPhiNoOpTest(unittest.TestCase):

    def test_scrub_off_leaves_envelope_unchanged(self):
        msg_plain = _file_to_message(
            open(FIXTURE, "rb"), "json")
        msg_explicit_off = _file_to_message(
            open(FIXTURE, "rb"), "json", scrub_phi=False)
        self.assertEqual(msg_plain, msg_explicit_off)


def test_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(ScrubPhiPolicyTest))
    suite.addTests(loader.loadTestsFromTestCase(ScrubPhiMetadataTest))
    suite.addTests(loader.loadTestsFromTestCase(ScrubPhiNoOpTest))
    return suite
