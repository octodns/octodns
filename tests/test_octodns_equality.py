#
#
#

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

        # hash
        self.assertEqual(hash(one), hash(one))
        self.assertEqual(hash(one), hash(same))
        # only a & b are considered, c is ignored, same as equality
        self.assertEqual(hash(one), hash(matches))
        self.assertNotEqual(hash(one), hash(doesnt))

        values = {one, same, matches, doesnt}
        # one, same, & matches all hash/compare equal so only 2 unique
        # members end up in the set
        self.assertEqual(2, len(values))
        self.assertIn(one, values)
        self.assertIn(doesnt, values)

    def test_not_implemented(self):
        class MissingMethod(EqualityTupleMixin):
            pass

        with self.assertRaises(NotImplementedError):
            MissingMethod() == MissingMethod()

    def test_hash_requires_hashable_equality_tuple(self):
        class Unhashable(EqualityTupleMixin):
            def _equality_tuple(self):
                return (1, [2, 3])

        with self.assertRaises(TypeError):
            hash(Unhashable())
