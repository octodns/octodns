#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import dns.zone
from dns.exception import DNSException

from mock import patch
from six import text_type
from unittest import TestCase

from octodns.source.axfr import AxfrSource, AxfrSourceZoneTransferFailed, \
    ZoneFileSource, ZoneFileSourceLoadFailure
from octodns.zone import Zone
from octodns.record import ValidationError


class TestAxfrSource(TestCase):
    source = AxfrSource('test', 'localhost')

    forward_zonefile = dns.zone.from_file('./tests/zones/unit.tests.',
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
                          text_type(ctx.exception))


class TestZoneFileSource(TestCase):
    source = ZoneFileSource('test', './tests/zones')

    def test_populate(self):
        # Valid zone file in directory
        valid = Zone('unit.tests.', [])
        self.source.populate(valid)
        self.assertEquals(11, len(valid.records))

        # 2nd populate does not read file again
        again = Zone('unit.tests.', [])
        self.source.populate(again)
        self.assertEquals(11, len(again.records))

        # bust the cache
        del self.source._zone_records[valid.name]

        # No zone file in directory
        missing = Zone('missing.zone.', [])
        self.source.populate(missing)
        self.assertEquals(0, len(missing.records))

        # Zone file is not valid
        with self.assertRaises(ZoneFileSourceLoadFailure) as ctx:
            zone = Zone('invalid.zone.', [])
            self.source.populate(zone)
        self.assertEquals('The DNS zone has no NS RRset at its origin.',
                          text_type(ctx.exception))

        # Records are not to RFC (lenient=False)
        with self.assertRaises(ValidationError) as ctx:
            zone = Zone('invalid.records.', [])
            self.source.populate(zone)
        self.assertEquals('Invalid record _invalid.invalid.records.\n'
                          '  - invalid name for SRV record',
                          text_type(ctx.exception))

        # Records are not to RFC, but load anyhow (lenient=True)
        invalid = Zone('invalid.records.', [])
        self.source.populate(invalid, lenient=True)
        self.assertEquals(12, len(invalid.records))
