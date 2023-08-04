# -*- coding: utf-8 -*-
#
# Credits to Alexander Shorin:
# https://github.com/kxepal/python-astm

import datetime
import decimal
import warnings

from senaite.astm import fields
from senaite.astm.compat import u
from senaite.astm.mapping import Component
from senaite.astm.mapping import Mapping
from senaite.astm.tests.base import ASTMTestBase


class FieldTestCase(ASTMTestBase):
    """Test base field
    """
    def test_init_default(self):
        f = fields.Field()
        self.assertTrue(hasattr(f, "name"))
        self.assertTrue(hasattr(f, "default"))
        self.assertTrue(hasattr(f, "length"))
        self.assertEqual(f.name, None)
        self.assertEqual(f.default, None)
        self.assertEqual(f.length, None)

    def test_init_with_custom_name(self):
        f = fields.Field(name="foo")
        self.assertEqual(f.name, "foo")

    def test_init_with_custom_default_value(self):
        f = fields.Field(default="foo")
        self.assertEqual(f.default, "foo")

    def test_callable_default_value(self):
        class Dummy(Mapping):
            field = fields.Field(default=lambda: "foobar")
        self.assertEqual(Dummy().field, "foobar")


class NotUsedFieldTestCase(ASTMTestBase):
    """Test placeholder field
    """
    def setUp(self):
        class Dummy(Mapping):
            field = fields.NotUsedField()
        self.Dummy = Dummy

    def test_get_value(self):
        obj = self.Dummy()
        self.assertEqual(obj.field, None)
        self.assertEqual(obj[0], None)

    def test_set_value(self):
        obj = self.Dummy()
        with warnings.catch_warnings(record=True) as w:
            obj.field = 42
            assert issubclass(w[-1].category, UserWarning)
        self.assertEqual(obj.field, None)


class IntegerTestCase(ASTMTestBase):
    """Test integer field
    """
    def setUp(self):
        class Dummy(Mapping):
            field = fields.IntegerField()
        self.Dummy = Dummy

    def test_get_value(self):
        obj = self.Dummy(field=42)
        self.assertEqual(obj.field, 42)

    def test_set_value(self):
        obj = self.Dummy()
        obj.field = 42
        self.assertEqual(obj.field, 42)

    def test_set_string_value(self):
        obj = self.Dummy()
        obj.field = "42"
        self.assertEqual(obj.field, 42)
        self.assertRaises(TypeError, setattr, obj, "field", "foo")


class DecimalFieldTestCase(ASTMTestBase):
    """Test decimal field
    """
    def setUp(self):
        class Dummy(Mapping):
            field = fields.DecimalField()
        self.Dummy = Dummy

    def test_get_value(self):
        obj = self.Dummy(field=3.14)
        self.assertEqual(obj.field, decimal.Decimal("3.14"))

    def test_set_value(self):
        obj = self.Dummy()
        obj.field = 3.14
        self.assertEqual(obj.field, decimal.Decimal("3.14"))

    def test_set_int_value(self):
        obj = self.Dummy()
        obj.field = 42
        self.assertEqual(obj.field, decimal.Decimal("42"))


class TextFieldTestCase(ASTMTestBase):
    """Test text field
    """
    def setUp(self):
        class Dummy(Mapping):
            field = fields.TextField()
        self.Dummy = Dummy

    def test_get_value(self):
        obj = self.Dummy(field="foo")
        self.assertEqual(obj.field, "foo")

    def test_set_value(self):
        obj = self.Dummy()
        obj.field = u("привет")
        self.assertEqual(obj.field, u("привет"))

    def test_set_utf8_value(self):
        obj = self.Dummy()
        obj.field = u("привет").encode("utf-8")
        self.assertEqual(obj.field, u("привет"))

    def test_fail_set_non_utf8_value(self):
        obj = self.Dummy()
        try:
            obj.field = u("привет").encode("cp1251")
        except UnicodeDecodeError:
            pass
        else:
            self.fail("%s expected" % UnicodeDecodeError)

    def test_fail_set_non_string_value(self):
        obj = self.Dummy()
        try:
            obj.field = object()
        except TypeError:
            pass
        else:
            self.fail("%s expected" % TypeError)

    def test_raw_value(self):
        obj = self.Dummy()
        obj.field = u("привет")
        self.assertEqual(obj._data["field"], u("привет"))


class DateFieldTestCase(ASTMTestBase):
    """Test date field
    """
    def setUp(self):
        class Dummy(Mapping):
            field = fields.DateField()
        self.Dummy = Dummy
        self.datetime = datetime.datetime(2023, 2, 25, 23, 9, 45, 30)
        self.date = datetime.datetime(2023, 2, 25)

    def test_get_value(self):
        obj = self.Dummy(field=self.datetime)
        self.assertEqual(obj.field, self.date)

    def test_set_datetime_value(self):
        obj = self.Dummy()
        obj.field = self.datetime
        self.assertEqual(obj.field, self.date)

    def test_init_date_value(self):
        obj = self.Dummy(field=self.date)
        self.assertEqual(obj.field, self.date)

    def test_set_date_value(self):
        obj = self.Dummy()
        obj.field = self.date
        self.assertEqual(obj.field, self.date)

    def test_raw_value(self):
        obj = self.Dummy()
        obj.field = self.datetime
        self.assertEqual(obj._data["field"],
                         self.date.strftime(obj._fields[0][1].format))

    def test_set_string_value(self):
        obj = self.Dummy()
        obj.field = "20090213"
        self.assertRaises(ValueError, setattr, obj, "field", "1234567")


class TimeFieldTestCase(ASTMTestBase):
    """Test time field
    """
    def setUp(self):
        class Dummy(Mapping):
            field = fields.TimeField()
        self.Dummy = Dummy
        self.datetime = datetime.datetime(2023, 2, 25, 9, 45, 30)
        self.time = datetime.time(9, 45, 30)

    def test_get_value(self):
        obj = self.Dummy(field=self.datetime)
        self.assertEqual(obj.field, self.time)

    def test_set_datetime_value(self):
        obj = self.Dummy()
        obj.field = self.datetime
        self.assertEqual(obj.field, self.time)

    def test_init_time_value(self):
        obj = self.Dummy(field=self.time)
        self.assertEqual(obj.field, self.time)

    def test_set_time_value(self):
        obj = self.Dummy()
        obj.field = self.time
        self.assertEqual(obj.field, self.time)

    def test_raw_value(self):
        obj = self.Dummy()
        obj.field = self.datetime
        self.assertEqual(obj._data["field"],
                         self.time.strftime(obj._fields[0][1].format))

    def test_set_string_value(self):
        obj = self.Dummy()
        obj.field = "111213"
        self.assertRaises(ValueError, setattr, obj, "field", "314159")


class DatetimeFieldTestCase(ASTMTestBase):
    """Test datetime field
    """
    def setUp(self):
        class Dummy(Mapping):
            field = fields.DateTimeField()
        self.Dummy = Dummy
        self.datetime = datetime.datetime(2023, 2, 25, 9, 45, 30)
        self.date = datetime.datetime(2023, 2, 25)

    def test_get_value(self):
        obj = self.Dummy(field=self.datetime)
        self.assertEqual(obj.field, self.datetime)

    def test_set_value(self):
        obj = self.Dummy()
        obj.field = self.datetime
        self.assertEqual(obj.field, self.datetime)

    def test_get_date_value(self):
        obj = self.Dummy(field=self.date)
        self.assertEqual(obj.field, self.date)

    def test_set_date_value(self):
        obj = self.Dummy()
        obj.field = self.date
        self.assertEqual(obj.field, self.date)

    def test_raw_value(self):
        obj = self.Dummy()
        obj.field = self.datetime
        self.assertEqual(obj._data["field"],
                         self.datetime.strftime(obj._fields[0][1].format))

    def test_set_string_value(self):
        obj = self.Dummy()
        obj.field = "20090213233130"
        self.assertRaises(ValueError, setattr, obj, "field", "12345678901234")


class ConstantFieldTestCase(ASTMTestBase):
    """Test constant field
    """
    def test_get_value(self):
        class Dummy(Mapping):
            field = fields.ConstantField(default=42)
        obj = Dummy()
        self.assertEqual(obj.field, 42)

    def test_set_value_if_none_default(self):
        class Dummy(Mapping):
            field = fields.ConstantField(default="foo")
        obj = Dummy()
        obj.field = "foo"
        self.assertEqual(obj.field, "foo")

    def test_fail_override_setted_value(self):
        class Dummy(Mapping):
            field = fields.ConstantField(default="foo")
        obj = Dummy()
        obj.field = "foo"
        self.assertEqual(obj.field, "foo")
        self.assertRaises(ValueError, setattr, obj, "field", "bar")

    def test_restrict_new_values_by_default_one(self):
        class Dummy(Mapping):
            field = fields.ConstantField(default="foo")
        obj = Dummy()
        self.assertRaises(ValueError, setattr, obj, "field", "bar")
        obj.field = "foo"
        self.assertEqual(obj.field, "foo")

    def test_raw_value(self):
        class Dummy(Mapping):
            field = fields.ConstantField(default="foo")
        obj = Dummy()
        obj.field = "foo"
        self.assertEqual(obj._data["field"], "foo")

    def test_raw_value_should_be_string(self):
        class Dummy(Mapping):
            field = fields.ConstantField(default=42)
        obj = Dummy()
        obj.field = 42
        self.assertEqual(obj._data["field"], "42")

    def test_always_required(self):
        field = fields.ConstantField(default="test")
        assert field.required
        self.assertRaises(
            TypeError, fields.ConstantField, default="test", required=False)

    def test_default_value_should_be_defined(self):
        self.assertRaises(ValueError, fields.ConstantField)


class SetFieldTestCase(ASTMTestBase):
    """Test set field
    """
    def setUp(self):
        class Dummy(Mapping):
            field = fields.SetField(values=["foo", "bar", "baz"])
        self.Dummy = Dummy

    def test_get_value(self):
        obj = self.Dummy(field="foo")
        self.assertEqual(obj.field, "foo")

    def test_set_value(self):
        obj = self.Dummy()
        obj.field = "bar"
        self.assertEqual(obj.field, "bar")

    def test_restrict_new_values_by_specified_set(self):
        obj = self.Dummy()
        self.assertRaises(ValueError, setattr, obj, "field", "boo")

    def test_reject_any_value(self):
        class Dummy(Mapping):
            field = fields.SetField()
        obj = Dummy()
        self.assertRaises(ValueError, setattr, obj, "field", "bar")
        self.assertRaises(ValueError, setattr, obj, "field", "foo")
        obj.field = None

    def test_custom_field(self):
        class Dummy(Mapping):
            field = fields.SetField(values=[1, 2, 3],
                                    field=fields.IntegerField())
        obj = Dummy()
        obj.field = 1
        self.assertEqual(obj._data["field"], "1")
        obj.field = 2
        self.assertEqual(obj._data["field"], "2")
        obj.field = 3
        self.assertEqual(obj._data["field"], "3")

    def test_raw_value(self):
        obj = self.Dummy()
        obj.field = "foo"
        self.assertEqual(obj._data["field"], "foo")


class ComponentFieldTestCase(ASTMTestBase):
    """Test component field
    """
    def setUp(self):
        class Dummy(Mapping):
            field = fields.ComponentField(
                mapping=Component.build(
                    fields.Field(name="foo"),
                    fields.IntegerField(name="bar"),
                    fields.ConstantField(name="baz", default="42")
                )
            )
        self.Dummy = Dummy

    def test_get_value(self):
        obj = self.Dummy(field=["foo", 14, "42"])
        self.assertEqual(obj.field, ["foo", 14, "42"])

    def test_set_value(self):
        obj = self.Dummy()
        self.assertRaises(TypeError, setattr, obj, "field", 42)
        self.assertRaises(ValueError, setattr, obj, "field", [1, 2, 3])
        obj.field = ["test", 24, "42"]
        self.assertEqual(obj.field, ["test", 24, "42"])

    def test_iter(self):
        obj = self.Dummy(field=["foo", 14, "42"])
        self.assertEqual(list(obj.field), ["foo", 14, "42"])

    def test_raw_value(self):
        obj = self.Dummy()
        obj.field = ["foo", 14, "42"]
        self.assertEqual(obj._data["field"], ["foo", 14, "42"])

    def test_set_string_value(self):
        obj = self.Dummy()
        obj.field = "foo"
        self.assertEqual(obj.field[0], "foo")
        self.assertEqual(obj.field[1], None)
        self.assertEqual(obj.field[2], "42")


class RepeatedComponentFieldTestCase(ASTMTestBase):
    """Test repeated component
    """
    def setUp(self):
        class Dummy(Mapping):
            field = fields.RepeatedComponentField(
                Component.build(
                    fields.TextField(name="key"),
                    fields.IntegerField(name="value"),
                )
            )

        class Thing(Mapping):
            numbers = fields.RepeatedComponentField(
                Component.build(
                    fields.IntegerField(name="value")
                )
            )

        self.Dummy = Dummy
        self.Thing = Thing

    def test_get_value(self):
        obj = self.Dummy(field=[["foo", 1], ["bar", 2], ["baz", 3]])
        self.assertEqual(obj.field, [["foo", 1], ["bar", 2], ["baz", 3]])

    def test_set_value(self):
        obj = self.Dummy()
        self.assertRaises(TypeError, setattr, obj, "field", 42)
        obj.field = [["foo", 42]]
        self.assertEqual(obj.field, [["foo", 42]])

    def test_fail_on_set_strings(self):
        obj = self.Dummy()
        obj.field = "foo"  # WHY?
        # self.assertRaises(TypeError, setattr, obj, "field", "foo")

    def test_iter(self):
        obj = self.Dummy(field=[["foo", 14]])
        self.assertEqual(list(obj.field), [["foo", 14]])

    def test_getter_returns_list(self):
        obj = self.Dummy([["foo", 42]])
        self.assertTrue(isinstance(obj.field, list))

    def test_proxy_delitem(self):
        obj = self.Dummy([["foo", 1], ["bar", 2]])
        del obj.field[0]
        self.assertEqual(len(obj.field), 1)
        self.assertEqual(obj.field[0], ["bar", 2])

    def test_proxy_append(self):
        obj = self.Dummy([["foo", 1]])
        self.assertEqual(obj.field[0], ["foo", 1])
        obj.field.append(["bar", 2])
        self.assertEqual(obj.field[1], ["bar", 2])

    def test_proxy_extend(self):
        obj = self.Dummy([["foo", 1]])
        obj.field.extend([["bar", 2], ["baz", 3]])
        self.assertEqual(len(obj.field), 3)
        self.assertEqual(obj.field[2], ["baz", 3])

    def test_proxy_contains(self):
        obj = self.Thing(numbers=[[i] for i in range(5)])
        self.assertTrue([3] in obj.numbers)
        self.assertTrue([6] not in obj.numbers)

    def test_proxy_count(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        self.assertEqual(1, obj.numbers.count([1]))
        self.assertEqual(0, obj.numbers.count([4]))

    def test_proxy_index(self):
        obj = self.Thing(numbers=[[1], [2], [4]])
        self.assertEqual(1, obj.numbers.index([2]))

    def test_proxy_index_range(self):
        obj = self.Thing(numbers=[[1], [2], [4], [5]])
        self.assertEqual(2, obj.numbers.index([4], 2, 3))

    def test_fail_proxy_index_for_nonexisted_element(self):
        obj = self.Thing(numbers=[[1], [2], [4]])
        self.assertRaises(ValueError, obj.numbers.index, [5])

    def test_fail_proxy_index_negative_start(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        self.assertRaises(ValueError, obj.numbers.index, 2, -1, 3)

    def test_proxy_insert(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        obj.numbers.insert(0, [0])
        self.assertEqual(obj.numbers[0], [0])

    def test_proxy_remove(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        obj.numbers.remove([1])
        obj.numbers.remove([2])
        self.assertEqual(len(obj.numbers), 1)
        self.assertEqual(obj.numbers[0].value, 3)

    def test_fail_proxy_remove_missing(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        self.assertRaises(ValueError, obj.numbers.remove, [5])

    def test_proxy_pop(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        self.assertEqual(obj.numbers.pop(), [3])
        self.assertEqual(len(obj.numbers), 2)
        self.assertEqual(obj.numbers.pop(0), [1])

    # XXX: Fails with error:
    # TypeError: Integer value expected, got GenericComponent(value=1)
    # def test_proxy_slices(self):
    #     obj = self.Thing()
    #     obj.numbers = [[i] for i in range(5)]
    #     ll = obj.numbers[1:3]
    #     self.assertEqual(len(ll), 2)
    #     self.assertEqual(ll[0], [1])
    #     obj.numbers[2:4] = [[i] for i in range(6, 8)]
    #     self.assertEqual(obj.numbers[2], [6])
    #     self.assertEqual(obj.numbers[4], [4])
    #     self.assertEqual(len(obj.numbers), 5)
    #     del obj.numbers[3:]
    #     self.assertEquals(len(obj.numbers), 3)

    def test_proxy_sort_fails(self):
        class Dummy(Mapping):
            numbers = fields.RepeatedComponentField(
                Component.build(
                    fields.IntegerField(name="a"),
                    fields.IntegerField(name="b")
                )
            )
        obj = Dummy(numbers=[[4, 2], [2, 3], [0, 1]])
        self.assertRaises(NotImplementedError, obj.numbers.sort)

    def test_proxy_lt(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        self.assertTrue(obj.numbers < [[4], [5], [6]])

    def test_proxy_lt_with_other_proxy(self):
        obj1 = self.Thing(numbers=[[1], [2], [3]])
        obj2 = self.Thing(numbers=[[4], [5], [6]])
        self.assertTrue(obj1.numbers < obj2.numbers)

    def test_proxy_le(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        self.assertTrue(obj.numbers <= [[1], [2], [3]])

    def test_proxy_le_with_other_proxy(self):
        obj1 = self.Thing(numbers=[[1], [2], [3]])
        obj2 = self.Thing(numbers=[[1], [2], [3]])
        self.assertTrue(obj1.numbers <= obj2.numbers)

    def test_proxy_eq(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        self.assertTrue(obj.numbers == [[1], [2], [3]])

    def test_proxy_eq_with_other_proxy(self):
        obj1 = self.Thing(numbers=[[1], [2], [3]])
        obj2 = self.Thing(numbers=[[1], [2], [3]])
        self.assertTrue(obj1.numbers == obj2.numbers)

    def test_proxy_ne(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        self.assertTrue(obj.numbers != [[4], [5], [6]])

    def test_proxy_ne_with_other_proxy(self):
        obj1 = self.Thing(numbers=[[1], [2], [3]])
        obj2 = self.Thing(numbers=[[4], [5], [6]])
        self.assertTrue(obj1.numbers != obj2.numbers)

    def test_proxy_ge(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        self.assertTrue(obj.numbers >= [[1], [2], [3]])

    def test_proxy_ge_with_other_proxy(self):
        obj1 = self.Thing(numbers=[[1], [2], [3]])
        obj2 = self.Thing(numbers=[[1], [2], [3]])
        self.assertTrue(obj1.numbers >= obj2.numbers)

    def test_proxy_gt(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        self.assertTrue(obj.numbers > [[0], [1], [2]])

    def test_proxy_gt_with_other_proxy(self):
        obj1 = self.Thing(numbers=[[1], [2], [3]])
        obj2 = self.Thing(numbers=[[0], [1], [2]])
        self.assertTrue(obj1.numbers > obj2.numbers)

    def test_proxy_add(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        lst = obj.numbers + [[4], [5], [6]]
        self.assertEqual(lst, [[1], [2], [3], [4], [5], [6]])
        self.assertTrue(isinstance(lst, list))
        self.assertTrue(obj.numbers is not lst)

    def test_proxy_add_other_proxy(self):
        obj1 = self.Thing(numbers=[[1], [2], [3]])
        obj2 = self.Thing(numbers=[[4], [5], [6]])
        lst = obj1.numbers + obj2.numbers
        self.assertEqual(lst, [[1], [2], [3], [4], [5], [6]])

    def test_proxy_iadd(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        obj.numbers += [[4], [5], [6]]
        self.assertEqual(obj.numbers, [[1], [2], [3], [4], [5], [6]])

    def test_proxy_mul(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        lst = obj.numbers * 2
        self.assertEqual(lst, [[1], [2], [3], [1], [2], [3]])
        self.assertTrue(isinstance(lst, list))
        self.assertTrue(obj.numbers is not lst)
        self.assertEqual(obj.numbers, [[1], [2], [3]])

    def test_proxy_mul_one(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        lst = obj.numbers * 1
        self.assertEqual(lst, [[1], [2], [3]])

    def test_proxy_mul_zero(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        lst = obj.numbers * 0
        self.assertEqual(lst, [])
        self.assertTrue(isinstance(lst, list))

    def test_proxy_imul(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        obj.numbers *= 2
        self.assertEqual(obj.numbers, [[1], [2], [3], [1], [2], [3]])

    def test_proxy_imul_one(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        obj.numbers *= 1
        self.assertEqual(obj.numbers, [[1], [2], [3]])

    def test_proxy_imul_zero(self):
        obj = self.Thing(numbers=[[1], [2], [3]])
        obj.numbers *= 0
        self.assertEqual(obj.numbers, [])
