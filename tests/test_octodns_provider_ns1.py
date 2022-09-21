#
#
#

from unittest import TestCase


class TestNs1Provider(TestCase):
    def test_missing(self):
        with self.assertRaises(ModuleNotFoundError):
            from octodns.provider.ns1 import Ns1Provider

            Ns1Provider
