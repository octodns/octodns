#
#
#

from unittest import TestCase


class TestMythicBeastsShim(TestCase):
    def test_missing(self):
        with self.assertRaises(ModuleNotFoundError):
            from octodns.provider.mythicbeasts import MythicBeastsProvider

            MythicBeastsProvider
