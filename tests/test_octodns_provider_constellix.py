#
#
#

from unittest import TestCase


class TestConstellixShim(TestCase):
    def test_missing(self):
        with self.assertRaises(ModuleNotFoundError):
            from octodns.provider.constellix import ConstellixProvider

            ConstellixProvider
