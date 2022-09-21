#
#
#

from unittest import TestCase


class TestDigitalOceanShim(TestCase):
    def test_missing(self):
        with self.assertRaises(ModuleNotFoundError):
            from octodns.provider.digitalocean import DigitalOceanProvider

            DigitalOceanProvider
