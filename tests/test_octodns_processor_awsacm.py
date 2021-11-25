#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from octodns.processor.awsacm import AwsAcmMangingProcessor
from octodns.record import Record
from octodns.zone import Zone

zone = Zone('unit.tests.', [])
records = {
    'root': Record.new(zone, '_deadbeef', {
        'ttl': 30,
        'type': 'CNAME',
        'value': '_0123456789abcdef.acm-validations.aws.',
    }),
    'sub': Record.new(zone, '_deadbeef.sub', {
        'ttl': 30,
        'type': 'CNAME',
        'value': '_0123456789abcdef.acm-validations.aws.',
    }),
    'not-cname': Record.new(zone, '_deadbeef.not-cname', {
        'ttl': 30,
        'type': 'AAAA',
        'value': '::1',
    }),
    'not-acm': Record.new(zone, '_not-acm', {
        'ttl': 30,
        'type': 'CNAME',
        'value': 'localhost.unit.tests.',
    }),
}


class TestAwsAcmMangingProcessor(TestCase):

    def test_process_zones(self):
        acm = AwsAcmMangingProcessor('acm')

        source = Zone(zone.name, [])
        # Unrelated stuff that should be untouched
        source.add_record(records['not-cname'])
        source.add_record(records['not-acm'])
        # ACM records that should be ignored
        source.add_record(records['root'])
        source.add_record(records['sub'])

        got = acm.process_source_zone(source)
        self.assertEqual([
            '_deadbeef.not-cname',
            '_not-acm',
        ], sorted([r.name for r in got.records]))

        existing = Zone(zone.name, [])
        # Unrelated stuff that should be untouched
        existing.add_record(records['not-cname'])
        existing.add_record(records['not-acm'])
        # Stuff that will be ignored
        existing.add_record(records['root'])
        existing.add_record(records['sub'])

        got = acm.process_target_zone(existing)
        self.assertEqual([
            '_deadbeef.not-cname',
            '_not-acm'
        ], sorted([r.name for r in got.records]))
