# -*- coding: utf-8 -*-

import re
import unittest

from senaite.astm import records
from senaite.astm.core.instrument import AmbiguousInstrumentError
from senaite.astm.core.instrument import Instrument
from senaite.astm.core.instrument import find_instrument
from senaite.astm.core.instrument import register_instrument
from senaite.astm.core.instrument import registered_instruments
from senaite.astm.core.instrument import unregister_instrument


def _make_record_map():
    return {
        "H": records.HeaderRecord,
        "P": records.PatientRecord,
        "O": records.OrderRecord,
        "R": records.ResultRecord,
        "C": records.CommentRecord,
        "L": records.TerminatorRecord,
    }


class InstrumentRegistryTest(unittest.TestCase):

    def setUp(self):
        self._registered = []

    def tearDown(self):
        for name in self._registered:
            unregister_instrument(name)

    def _register(self, cls):
        self._registered.append(cls.name)
        return register_instrument(cls)

    def test_registers_and_resolves_by_header(self):
        @self._register
        class FakeAlpha(Instrument):
            name = "test:alpha"
            header_regex = re.compile(rb".*FakeAlpha\^")
            record_map = _make_record_map()

        header = b"1H|\\^&|||FakeAlpha^v1|||||EPR||P|1|20260512|"
        instrument = find_instrument(header)
        self.assertIsNotNone(instrument)
        self.assertEqual(instrument.name, "test:alpha")
        self.assertIn(instrument, registered_instruments())

    def test_unknown_header_returns_none(self):
        @self._register
        class FakeBeta(Instrument):
            name = "test:beta"
            header_regex = re.compile(rb".*FakeBeta\^")
            record_map = _make_record_map()

        self.assertIsNone(find_instrument(b"1H|\\^&|||Other^|||"))

    def test_overlapping_regexes_raise(self):
        @self._register
        class FakeOne(Instrument):
            name = "test:one"
            header_regex = re.compile(rb".*Shared\^")
            record_map = _make_record_map()

        @self._register
        class FakeTwo(Instrument):
            name = "test:two"
            header_regex = re.compile(rb".*Shared\^")
            record_map = _make_record_map()

        with self.assertRaises(AmbiguousInstrumentError):
            find_instrument(b"1H|\\^&|||Shared^v|||")

    def test_preparse_defaults_to_passthrough(self):
        @self._register
        class FakeGamma(Instrument):
            name = "test:gamma"
            header_regex = re.compile(rb".*Gamma\^")
            record_map = _make_record_map()

        raw = b"1H|\\^&|||Gamma^|||"
        self.assertEqual(FakeGamma().preparse(raw), raw)

    def test_preparse_hook_can_rewrite_bytes(self):
        @self._register
        class FakeDelta(Instrument):
            name = "test:delta"
            header_regex = re.compile(rb".*Delta\^")
            record_map = _make_record_map()

            def preparse(self, raw):
                return raw.upper()

        out = FakeDelta().preparse(b"hello")
        self.assertEqual(out, b"HELLO")

    def test_metadata_defaults_to_empty(self):
        @self._register
        class FakeEpsilon(Instrument):
            name = "test:epsilon"
            header_regex = re.compile(rb".*Epsilon\^")
            record_map = _make_record_map()

        self.assertEqual(FakeEpsilon().get_metadata(wrapper=None), {})

    def test_registration_validates_required_attributes(self):
        class Missing(Instrument):
            pass

        with self.assertRaises(ValueError):
            register_instrument(Missing)

        class MissingRegex(Instrument):
            name = "test:no-regex"
            record_map = _make_record_map()

        with self.assertRaises(ValueError):
            register_instrument(MissingRegex)

        class MissingMap(Instrument):
            name = "test:no-map"
            header_regex = re.compile(rb".*x")

        with self.assertRaises(ValueError):
            register_instrument(MissingMap)

    def test_non_instrument_subclass_rejected(self):
        class NotAnInstrument(object):
            name = "test:bogus"

        with self.assertRaises(TypeError):
            register_instrument(NotAnInstrument)


class WrapperRegistryIntegrationTest(unittest.TestCase):
    """Wrapper should consult the registry before falling back to
    the legacy pkgutil discovery.
    """

    def setUp(self):
        self._registered = []

    def tearDown(self):
        for name in self._registered:
            unregister_instrument(name)

    def _register(self, cls):
        self._registered.append(cls.name)
        return register_instrument(cls)

    def test_wrapper_uses_registered_instrument(self):
        from senaite.astm.wrapper import Wrapper

        custom_map = {"H": records.HeaderRecord}

        @self._register
        class FakeMega(Instrument):
            name = "test:mega"
            header_regex = re.compile(rb".*MegaProbe\^")
            record_map = custom_map

        wrapper = Wrapper([b"1H|\\^&|||MegaProbe^|||"])
        self.assertIs(wrapper.instrument.__class__, FakeMega)
        self.assertEqual(set(wrapper.mapping), {"H"})

    def test_wrapper_falls_back_to_legacy_discovery(self):
        from senaite.astm.wrapper import Wrapper

        # Header that matches the existing pkgutil-discovered
        # Afinion 2 module; no registry entry needed.
        header = b"1H|\\^&|||Afinion 2 Analyzer^^AF0000030|||||EPR||P|1|"
        wrapper = Wrapper([header])
        self.assertIsNone(wrapper.instrument)
        # Legacy mapping must still resolve through pkgutil.
        self.assertIn("H", wrapper.mapping)
