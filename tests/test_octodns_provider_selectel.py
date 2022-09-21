#
#
#

from unittest import TestCase


class TestSelectelShim(TestCase):
    def test_missing(self):
        with self.assertRaises(ModuleNotFoundError):
            from octodns.provider.selectel import SelectelProvider

            SelectelProvider
