#
#
#

from unittest import TestCase


class TestRoute53Provider(TestCase):
    def test_missing(self):
        with self.assertRaises(ModuleNotFoundError):
            from octodns.provider.route53 import Route53Provider

            Route53Provider
