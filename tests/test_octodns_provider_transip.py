#
#
#

from unittest import TestCase


class TestTransipShim(TestCase):
    def test_missing(self):
        with self.assertRaises(ModuleNotFoundError):
            from octodns.provider.transip import TransipProvider

            TransipProvider
