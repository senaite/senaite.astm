# -*- coding: utf-8 -*-
#
# Credits to Alexander Shorin:
# https://github.com/kxepal/python-astm

from senaite.astm import fields
from senaite.astm.mapping import Component
from senaite.astm.mapping import Mapping
from senaite.astm.tests.base import ASTMTestBase


class MappingTestCase(ASTMTestBase):

    def setUp(self):

        class Dummy(Mapping):
            foo = fields.Field(default="bar")
            bar = fields.ComponentField(mapping=Component.build(
                fields.IntegerField(name="a"),
                fields.IntegerField(name="b"),
                fields.IntegerField(name="c"),
            ), default=[1, 2, 3])

        class Thing(Mapping):
            numbers = fields.RepeatedComponentField(
                Component.build(
                    fields.IntegerField(name="a"),
                    fields.IntegerField(name="b")
                )
            )
        self.Dummy = Dummy
        self.Thing = Thing

    def test_equal(self):
        obj = self.Dummy("foo", [3, 2, 1])
        self.assertEqual(obj, ["foo", (3, 2, 1)])
        self.assertNotEqual(obj, ["foo"])

    def test_iter(self):
        obj = self.Dummy("foo", [3, 2, 1])
        self.assertEqual(list(obj), ["foo", [3, 2, 1]])

    def test_len(self):
        obj = self.Dummy("foo", [3, 2, 1])
        self.assertEqual(len(obj), 2)
        self.assertEqual(len(obj.bar), 3)

    def test_contains(self):
        obj = self.Dummy("foo", [3, 2, 1])
        assert "foo" in obj

    def test_getitem(self):
        obj = self.Dummy("foo", [3, 2, 1])
        self.assertEqual(obj[1][0], 3)

    def test_setitem(self):
        obj = self.Dummy("foo", [3, 2, 1])
        obj[1][0] = 42
        self.assertEqual(obj[1][0], 42)

    def test_delitem(self):
        obj = self.Dummy("foo", [3, 2, 1])
        del obj[1][1]
        self.assertEqual(obj[1][1], None)

    def test_to_astm_record(self):
        obj = self.Dummy("foo", [3, 2, 1])
        self.assertEqual(obj.to_astm(), ["foo", ["3", "2", "1"]])
        obj = self.Thing(numbers=[[4, 2], [2, 3], [0, 1]])
        self.assertEqual(obj.to_astm(), [[["4", "2"], ["2", "3"], ["0", "1"]]])

    def test_required_field(self):
        class Dummy(Mapping):
            field = fields.Field(required=True)
        obj = Dummy()
        self.assertTrue(obj.field is None)
        self.assertRaises(ValueError, obj.to_astm)

    def test_field_max_length(self):
        class Dummy(Mapping):
            field = fields.Field(length=10)
        obj = Dummy()
        obj.field = "-" * 9
        obj.field = None
        obj.field = "-" * 10
        self.assertRaises(ValueError, setattr, obj, "field", "-" * 11)
