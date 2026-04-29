# -*- coding: utf-8 -*-
"""Golden-snapshot test for the JSON envelope shape.

Every fixture under tests/data/*.txt is run through Wrapper.to_dict()
and compared against a checked-in snapshot under tests/data/envelopes/.
Downstream LIMS consumers depend on this shape, so a diff here is a
contract break and must be deliberate.

Regenerating snapshots after an intentional change:

    python -m senaite.astm.tests.test_envelope_contract --regenerate

Adapter-only fixtures (mini_vidas.txt, spotchem_el.txt) parse via a
custom registered adapter and are exercised by their own test files,
not here.
"""

import glob
import json
import os
import unittest

from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.wrapper import Wrapper

# Fixtures that need an adapter to parse — covered by their own tests.
ADAPTER_ONLY_FIXTURES = {"mini_vidas.txt", "spotchem_el.txt"}


def normalize(obj):
    """Recursively coerce bytes to str so the dict is JSON-serialisable
    in a stable, diffable way."""
    if isinstance(obj, bytes):
        return obj.decode("latin-1")
    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize(v) for v in obj]
    return obj


# Some fixtures (cobas_c311, sysmex_xn550, sysmex_xp100) leave the
# H record `timestamp` slot empty in the raw frame, so the parser
# fills it with `datetime.now()` at parse time. That value would
# poison every snapshot run. Replace it with a stable placeholder
# before comparing.
VOLATILE_FIELDS = {"timestamp"}
VOLATILE_PLACEHOLDER = "<volatile>"


def strip_volatile(obj):
    if isinstance(obj, dict):
        return {
            k: VOLATILE_PLACEHOLDER if k in VOLATILE_FIELDS
            else strip_volatile(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [strip_volatile(v) for v in obj]
    return obj


def envelope_for(path):
    with open(path, "rb") as f:
        lines = [line.rstrip(b"\n") for line in f.readlines()]
    return strip_volatile(normalize(dict(Wrapper(lines).to_dict())))


def snapshot_path(fixture_path):
    name = os.path.basename(fixture_path).replace(".txt", ".json")
    return os.path.join(os.path.dirname(fixture_path), "envelopes", name)


class EnvelopeContractTest(ASTMTestBase):
    """Per-fixture golden snapshot.

    Generated dynamically so a new fixture under tests/data/ that
    parses without an adapter is automatically covered the moment its
    snapshot is committed.
    """


def _make_test(fixture_path):
    def test(self):
        expected_path = snapshot_path(fixture_path)
        self.assertTrue(
            os.path.exists(expected_path),
            "Missing snapshot for {}: regenerate with "
            "`python -m senaite.astm.tests.test_envelope_contract "
            "--regenerate`".format(os.path.basename(fixture_path)))
        with open(expected_path) as f:
            expected = json.load(f)
        actual = envelope_for(fixture_path)
        self.assertEqual(actual, expected)
    return test


def _attach_tests():
    test_dir = os.path.join(os.path.dirname(__file__), "data")
    for path in sorted(glob.glob(os.path.join(test_dir, "*.txt"))):
        name = os.path.basename(path)
        if name in ADAPTER_ONLY_FIXTURES:
            continue
        method_name = "test_envelope_" + name.replace(".txt", "")
        setattr(EnvelopeContractTest, method_name, _make_test(path))


_attach_tests()


def regenerate():
    """Rewrite every snapshot from the current parser output."""
    test_dir = os.path.join(os.path.dirname(__file__), "data")
    out_dir = os.path.join(test_dir, "envelopes")
    os.makedirs(out_dir, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(test_dir, "*.txt"))):
        name = os.path.basename(path)
        if name in ADAPTER_ONLY_FIXTURES:
            continue
        with open(snapshot_path(path), "w") as f:
            json.dump(envelope_for(path), f,
                      indent=2, sort_keys=True, default=str)
        print("wrote", snapshot_path(path))


if __name__ == "__main__":
    import sys
    if "--regenerate" in sys.argv:
        regenerate()
    else:
        unittest.main()
