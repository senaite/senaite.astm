# -*- coding: utf-8 -*-
"""Tests for `senaite-astm-send --scrub-phi`.

The flag redacts patient-identifying fields in the typed envelope
before serialisation so real captures can be replayed against a
dev / staging LIMS without leaking PHI. Only the JSON output is
scrubbed; raw ASTM / LIS2-A bytes are intentionally cleared so a
downstream consumer can't pull them back to the unredacted form.
"""

import json
import os
import unittest

from senaite.astm.core.envelope import Envelope
from senaite.astm.core.envelope import Metadata
from senaite.astm.sender import PHI_KEYS
from senaite.astm.sender import PHI_REDACTION
from senaite.astm.sender import _file_to_message
from senaite.astm.sender import _scrub_envelope_phi


HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "data")
FIXTURE = os.path.join(DATA_DIR, "yumizen_h500.txt")


def _envelope(scrub=False, phi_extra=()):
    msg = _file_to_message(
        open(FIXTURE, "rb"), "json",
        scrub_phi=scrub, phi_extra=phi_extra)
    return json.loads(msg)


class ScrubPhiTest(unittest.TestCase):

    def test_default_phi_keys_are_redacted(self):
        env = _envelope(scrub=True)
        for patient in env["P"]:
            for key in PHI_KEYS:
                if key in patient and patient[key]:
                    self.assertEqual(
                        patient[key], PHI_REDACTION,
                        "%s leaked: %r" % (key, patient[key]))

    def test_non_phi_fields_pass_through_unchanged(self):
        original = _envelope(scrub=False)
        scrubbed = _envelope(scrub=True)
        # Sex is not in PHI_KEYS — must not be redacted.
        for orig, scrub in zip(original["P"], scrubbed["P"]):
            if "sex" in orig:
                self.assertEqual(scrub.get("sex"), orig.get("sex"))

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

    def test_extra_field_is_redacted(self):
        # The bundled fixture's P record only has type/seq
        # populated, so verify --scrub-phi-extra-field at the
        # function level with a synthetic envelope.
        env = Envelope(metadata=Metadata())
        env.P.append({
            "type": "P",
            "seq": "1",
            "name": "Doe^John",
            "vendor_tag": "lab-internal-id-42",
        })
        _scrub_envelope_phi(env, extra_keys=("vendor_tag",))
        self.assertEqual(env.P[0]["name"], PHI_REDACTION)
        self.assertEqual(env.P[0]["vendor_tag"], PHI_REDACTION)
        # type / seq are not in the keys set
        self.assertEqual(env.P[0]["type"], "P")
        self.assertEqual(env.P[0]["seq"], "1")


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
    suite.addTests(loader.loadTestsFromTestCase(ScrubPhiTest))
    suite.addTests(loader.loadTestsFromTestCase(ScrubPhiNoOpTest))
    return suite
