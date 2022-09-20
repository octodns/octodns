#
#
#

from unittest import TestCase


class TestDynShim(TestCase):
    def test_missing(self):
        with self.assertRaises(ModuleNotFoundError):
            from octodns.provider.dyn import DynProvider

            DynProvider
