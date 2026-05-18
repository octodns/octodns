#
#
#

from unittest import TestCase

from octodns.equality import EqualityTupleMixin


class TestEqualityTupleMixin(TestCase):
    class Simple(EqualityTupleMixin):
        def __init__(self, a, b, c):
            self.a = a
            self.b = b
            self.c = c

        def _equality_tuple(self):
            return (self.a, self.b)

    def test_basics(self):

        one = self.Simple(1, 2, 3)
        same = self.Simple(1, 2, 3)
        matches = self.Simple(1, 2, 'ignored')
        doesnt = self.Simple(2, 3, 4)

        # equality
        self.assertEqual(one, one)
        self.assertEqual(one, same)
        self.assertEqual(same, one)
        # only a & c are considered
        self.assertEqual(one, matches)
        self.assertEqual(matches, one)
        self.assertNotEqual(one, doesnt)
        self.assertNotEqual(doesnt, one)

        # lt
        self.assertTrue(one < doesnt)
        self.assertFalse(doesnt < one)
        self.assertFalse(one < same)

        # le
        self.assertTrue(one <= doesnt)
        self.assertFalse(doesnt <= one)
        self.assertTrue(one <= same)

        # gt
        self.assertFalse(one > doesnt)
        self.assertTrue(doesnt > one)
        self.assertFalse(one > same)

        # ge
        self.assertFalse(one >= doesnt)
        self.assertTrue(doesnt >= one)
        self.assertTrue(one >= same)

    def test_not_implemented(self):
        class MissingMethod(EqualityTupleMixin):
            pass

        with self.assertRaises(NotImplementedError):
            MissingMethod() == MissingMethod()

    def test_mismatched(self):
        class NoEquality:
            pass

        has = self.Simple(1, 2, 3)
        doesnt = NoEquality()

        self.assertEqual(has.__eq__(doesnt), NotImplemented)
        self.assertEqual(has.__ne__(doesnt), NotImplemented)
        self.assertEqual(has.__lt__(doesnt), NotImplemented)
        self.assertEqual(has.__le__(doesnt), NotImplemented)
        self.assertEqual(has.__gt__(doesnt), NotImplemented)
        self.assertEqual(has.__ge__(doesnt), NotImplemented)
