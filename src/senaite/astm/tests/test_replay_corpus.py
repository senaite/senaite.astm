# -*- coding: utf-8 -*-
"""Replay real-traffic ASTM captures through :class:`Wrapper`.

The corpus under :envvar:`ASTM_REPLAY_DIR` is operator-supplied
(typically rsynced off a production capture directory) and contains
whatever bytes the upstream device emitted — including malformed,
truncated, and empty frames captured by accident. The point of this
test is regression detection, not perfect parsing: we want to know
when a refactor pushes the failure rate above its historical baseline.

The test passes when:

* less than :data:`MAX_FAILURE_RATIO` of files raise on parse,
* every successful parse declares the current envelope version.

When :envvar:`ASTM_REPLAY_DIR` is unset (CI) the test skips.
"""

import os
import unittest

from senaite.astm.core.envelope import ENVELOPE_VERSION
from senaite.astm.wrapper import Wrapper

REPLAY_DIR = os.environ.get("ASTM_REPLAY_DIR")

# Empirical baseline against a ~50k-file production corpus: ~3.1% fail
# (mostly truncated Roche c111 sessions where the recorder flushed
# before the trailing <CR><ETX>, plus a handful of malformed payloads).
# Anything materially above this threshold means a refactor regressed
# parsing for real traffic.
MAX_FAILURE_RATIO = 0.05


def _envelope_for(path):
    with open(path, "rb") as f:
        lines = [line.rstrip(b"\n") for line in f.readlines()]
    lines = [line for line in lines if line]
    return Wrapper(lines).to_envelope()


def _collect_files(root):
    paths = []
    for parent, _, names in os.walk(root):
        for name in names:
            if name.startswith("."):
                continue
            paths.append(os.path.join(parent, name))
    return sorted(paths)


@unittest.skipUnless(
    REPLAY_DIR and os.path.isdir(REPLAY_DIR),
    "ASTM_REPLAY_DIR not set or directory missing")
class ReplayCorpusTest(unittest.TestCase):

    def test_corpus_parses_within_tolerance(self):
        files = _collect_files(REPLAY_DIR)
        self.assertTrue(
            files, "%s contains no replay files" % REPLAY_DIR)

        failures = []
        version_mismatch = []
        for path in files:
            try:
                envelope = _envelope_for(path)
            except Exception as exc:
                failures.append((path, type(exc).__name__, str(exc)))
                continue
            if envelope.metadata.envelope_version != ENVELOPE_VERSION:
                version_mismatch.append(
                    (path, envelope.metadata.envelope_version))

        ratio = len(failures) / len(files)
        self.assertLess(
            ratio, MAX_FAILURE_RATIO,
            "replay failure rate %.4f exceeds tolerance %.4f "
            "(%d/%d files); sample failures:\n%s" % (
                ratio, MAX_FAILURE_RATIO,
                len(failures), len(files),
                "\n".join("%s: %s — %s" % f for f in failures[:5])))

        self.assertEqual(
            version_mismatch, [],
            "envelopes carried a stale envelope_version: %r"
            % version_mismatch[:5])
