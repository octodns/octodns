#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from octodns.equality import EqualityTupleMixin


class TestEqualityTupleMixin(TestCase):

    def test_basics(self):

        class Simple(EqualityTupleMixin):

            def __init__(self, a, b, c):
                self.a = a
                self.b = b
                self.c = c

            def _equality_tuple(self):
                return (self.a, self.b)

        one = Simple(1, 2, 3)
        same = Simple(1, 2, 3)
        matches = Simple(1, 2, 'ignored')
        doesnt = Simple(2, 3, 4)

        # equality
        self.assertEquals(one, one)
        self.assertEquals(one, same)
        self.assertEquals(same, one)
        # only a & c are considered
        self.assertEquals(one, matches)
        self.assertEquals(matches, one)
        self.assertNotEquals(one, doesnt)
        self.assertNotEquals(doesnt, one)

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
