#
#
#

from unittest import TestCase


class TestDnsimpleShim(TestCase):
    def test_missing(self):
        with self.assertRaises(ModuleNotFoundError):
            from octodns.provider.dnsimple import DnsimpleProvider

            DnsimpleProvider
