#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import dns.zone
from dns.exception import DNSException

from os.path import exists
from shutil import copyfile
from unittest import TestCase
from unittest.mock import patch

from octodns.source.axfr import AxfrSource, AxfrSourceZoneTransferFailed, \
    ZoneFileSource, ZoneFileSourceLoadFailure
from octodns.zone import Zone
from octodns.record import ValidationError


class TestAxfrSource(TestCase):
    source = AxfrSource('test', 'localhost')

    forward_zonefile = dns.zone.from_file('./tests/zones/unit.tests.tst',
                                          'unit.tests', relativize=False)

    @patch('dns.zone.from_xfr')
    def test_populate(self, from_xfr_mock):
        got = Zone('unit.tests.', [])

        from_xfr_mock.side_effect = [
            self.forward_zonefile,
            DNSException
        ]

        self.source.populate(got)
        self.assertEqual(15, len(got.records))

        with self.assertRaises(AxfrSourceZoneTransferFailed) as ctx:
            zone = Zone('unit.tests.', [])
            self.source.populate(zone)
        self.assertEqual('Unable to Perform Zone Transfer',
                         str(ctx.exception))


class TestZoneFileSource(TestCase):
    source = ZoneFileSource('test', './tests/zones', file_extension='.tst')

    def test_zonefiles_with_extension(self):
        source = ZoneFileSource('test', './tests/zones', '.extension')
        # Load zonefiles with a specified file extension
        valid = Zone('ext.unit.tests.', [])
        source.populate(valid)
        self.assertEqual(1, len(valid.records))

    def test_zonefiles_without_extension(self):
        # Windows doesn't let files end with a `.` so we add a .tst to them in
        # the repo and then try and create the `.` version we need for the
        # default case (no extension.)
        copyfile('./tests/zones/unit.tests.tst', './tests/zones/unit.tests.')
        # Unfortunately copyfile silently works and create the file without
        # the `.` so we have to check to see if it did that
        if exists('./tests/zones/unit.tests'):
            # It did so we need to skip this test, that means windows won't
            # have full code coverage, but skipping the test is going out of
            # our way enough for a os-specific/oddball case.
            self.skipTest('Unable to create unit.tests. (ending with .) so '
                          'skipping default filename testing.')

        source = ZoneFileSource('test', './tests/zones')
        # Load zonefiles without a specified file extension
        valid = Zone('unit.tests.', [])
        source.populate(valid)
        self.assertEqual(15, len(valid.records))

    def test_populate(self):
        # Valid zone file in directory
        valid = Zone('unit.tests.', [])
        self.source.populate(valid)
        self.assertEqual(15, len(valid.records))

        # 2nd populate does not read file again
        again = Zone('unit.tests.', [])
        self.source.populate(again)
        self.assertEqual(15, len(again.records))

        # bust the cache
        del self.source._zone_records[valid.name]

        # No zone file in directory
        missing = Zone('missing.zone.', [])
        self.source.populate(missing)
        self.assertEqual(0, len(missing.records))

        # Zone file is not valid
        with self.assertRaises(ZoneFileSourceLoadFailure) as ctx:
            zone = Zone('invalid.zone.', [])
            self.source.populate(zone)
        self.assertEqual('The DNS zone has no NS RRset at its origin.',
                         str(ctx.exception))

        # Records are not to RFC (lenient=False)
        with self.assertRaises(ValidationError) as ctx:
            zone = Zone('invalid.records.', [])
            self.source.populate(zone)
        self.assertEqual('Invalid record _invalid.invalid.records.\n'
                         '  - invalid name for SRV record',
                         str(ctx.exception))

        # Records are not to RFC, but load anyhow (lenient=True)
        invalid = Zone('invalid.records.', [])
        self.source.populate(invalid, lenient=True)
        self.assertEqual(12, len(invalid.records))
