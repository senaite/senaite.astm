# -*- coding: utf-8 -*-
"""Schema tests for the typed envelope.

These tests assert that:

- every checked-in golden snapshot validates against the
  :class:`Envelope` schema,
- omitted record-type buckets default to empty lists,
- :data:`ENVELOPE_VERSION` is exposed in the metadata,
- vendor-specific extras (e.g. Roche c111's parsed sender
  component) survive a round-trip through the model.
"""

import glob
import json
import os
import unittest

from pydantic import ValidationError

from senaite.astm.core.envelope import ENVELOPE_VERSION
from senaite.astm.core.envelope import Envelope


SNAPSHOT_DIR = os.path.join(
    os.path.dirname(__file__), "data", "envelopes")


def _snapshot_paths():
    return sorted(glob.glob(os.path.join(SNAPSHOT_DIR, "*.json")))


class EnvelopeSchemaTest(unittest.TestCase):
    """Every checked-in snapshot must round-trip through Envelope."""


def _make_validates(path):
    def test(self):
        with open(path) as f:
            data = json.load(f)
        envelope = Envelope.model_validate(data)
        self.assertEqual(
            envelope.metadata.envelope_version, ENVELOPE_VERSION)
    return test


for _path in _snapshot_paths():
    _name = os.path.basename(_path).replace(".json", "")
    setattr(
        EnvelopeSchemaTest,
        "test_validates_" + _name,
        _make_validates(_path))


class EnvelopeDefaultsTest(unittest.TestCase):
    """Defaults are deterministic across the whole envelope shape."""

    def _minimal(self, **extras):
        return Envelope(
            metadata={"astm": "", "lis2a": "", **extras})

    def test_default_envelope_version(self):
        envelope = self._minimal()
        self.assertEqual(
            envelope.metadata.envelope_version, ENVELOPE_VERSION)

    def test_record_buckets_default_to_empty_lists(self):
        envelope = self._minimal()
        for key in ("H", "P", "O", "R", "C", "M", "L", "Q"):
            self.assertEqual(
                getattr(envelope, key), [],
                "expected envelope.{} to default to []".format(key))

    def test_metadata_accepts_vendor_extras(self):
        envelope = self._minimal(instrument_type="c111", vendor="Roche")
        dumped = envelope.model_dump()
        self.assertEqual(dumped["metadata"]["instrument_type"], "c111")
        self.assertEqual(dumped["metadata"]["vendor"], "Roche")

    def test_metadata_requires_astm_and_lis2a(self):
        with self.assertRaises(ValidationError):
            Envelope(metadata={})

    def test_envelope_version_is_overridable(self):
        """Future schema bumps must keep older snapshots loadable
        without crashing — version comparison is a consumer concern.
        """
        envelope = Envelope(
            metadata={"astm": "", "lis2a": "",
                      "envelope_version": "0.9"})
        self.assertEqual(envelope.metadata.envelope_version, "0.9")
