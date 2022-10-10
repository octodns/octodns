#
#
#

from unittest import TestCase


class TestAxfrSource(TestCase):
    def test_missing(self):
        with self.assertRaises(ModuleNotFoundError):
            from octodns.source.axfr import AxfrSource

            AxfrSource

        with self.assertRaises(ModuleNotFoundError):
            from octodns.source.axfr import ZoneFileSource

            ZoneFileSource
