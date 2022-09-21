#
#
#

from unittest import TestCase


class TestCloudflareShim(TestCase):
    def test_missing(self):
        with self.assertRaises(ModuleNotFoundError):
            from octodns.provider.cloudflare import CloudflareProvider

            CloudflareProvider
