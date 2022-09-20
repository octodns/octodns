#
#
#

from unittest import TestCase


class TestGCoreShim(TestCase):
    def test_missing(self):
        with self.assertRaises(ModuleNotFoundError):
            from octodns.provider.gcore import GCoreProvider

            GCoreProvider
