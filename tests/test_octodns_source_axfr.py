#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import dns.zone
from dns.exception import DNSException

from mock import patch
from unittest import TestCase

from octodns.source.axfr import AxfrSource, AxfrSourceZoneTransferFailed
from octodns.zone import Zone


class TestAxfrSource(TestCase):
    source = AxfrSource('test', 'localhost')

    forward_zonefile = dns.zone.from_file('./tests/zones/unit.tests.db',
                                          'unit.tests', relativize=False)

    @patch('dns.zone.from_xfr')
    def test_populate(self, from_xfr_mock):
        got = Zone('unit.tests.', [])

        from_xfr_mock.side_effect = [
            self.forward_zonefile,
            DNSException
        ]

        self.source.populate(got)
        self.assertEquals(11, len(got.records))

        with self.assertRaises(AxfrSourceZoneTransferFailed) as ctx:
            zone = Zone('unit.tests.', [])
            self.source.populate(zone)
        self.assertEquals('Unable to Perform Zone Transfer',
                          ctx.exception.message)
