#
#
#

from unittest import TestCase

from octodns.processor.acme import AcmeMangingProcessor
from octodns.record import Record
from octodns.zone import Zone

zone = Zone('unit.tests.', [])
records = {
    'root-unowned': Record.new(
        zone,
        '_acme-challenge',
        {'ttl': 30, 'type': 'TXT', 'value': 'magic bit'},
    ),
    'sub-unowned': Record.new(
        zone,
        '_acme-challenge.sub-unowned',
        {'ttl': 30, 'type': 'TXT', 'value': 'magic bit'},
    ),
    'not-txt': Record.new(
        zone,
        '_acme-challenge.not-txt',
        {'ttl': 30, 'type': 'AAAA', 'value': '::1'},
    ),
    'not-acme': Record.new(
        zone, 'not-acme', {'ttl': 30, 'type': 'TXT', 'value': 'Hello World!'}
    ),
    'managed': Record.new(
        zone,
        '_acme-challenge.managed',
        {'ttl': 30, 'type': 'TXT', 'value': 'magic bit'},
    ),
    'owned': Record.new(
        zone,
        '_acme-challenge.owned',
        {'ttl': 30, 'type': 'TXT', 'values': ['*octoDNS*', 'magic bit']},
    ),
    'going-away': Record.new(
        zone,
        '_acme-challenge.going-away',
        {'ttl': 30, 'type': 'TXT', 'values': ['*octoDNS*', 'magic bit']},
    ),
}


class TestAcmeMangingProcessor(TestCase):
    def test_process_zones(self):
        acme = AcmeMangingProcessor('acme')

        source = Zone(zone.name, [])
        # Unrelated stuff that should be untouched
        source.add_record(records['not-txt'])
        source.add_record(records['not-acme'])
        # A managed acme that will have ownership value added
        source.add_record(records['managed'])

        got = acme.process_source_zone(source)
        self.assertEqual(
            ['_acme-challenge.managed', '_acme-challenge.not-txt', 'not-acme'],
            sorted([r.name for r in got.records]),
        )
        managed = None
        for record in got.records:
            if record.name.endswith('managed'):
                managed = record
                break
        self.assertTrue(managed)
        # Ownership was marked with an extra value
        self.assertEqual(['*octoDNS*', 'magic bit'], record.values)

        existing = Zone(zone.name, [])
        # Unrelated stuff that should be untouched
        existing.add_record(records['not-txt'])
        existing.add_record(records['not-acme'])
        # Stuff that will be ignored
        existing.add_record(records['root-unowned'])
        existing.add_record(records['sub-unowned'])
        # A managed acme that needs ownership value added
        existing.add_record(records['managed'])
        # A managed acme that has ownershp managed
        existing.add_record(records['owned'])
        # A managed acme that needs to go away
        existing.add_record(records['going-away'])

        got = acme.process_target_zone(existing)
        self.assertEqual(
            [
                '_acme-challenge.going-away',
                '_acme-challenge.managed',
                '_acme-challenge.not-txt',
                '_acme-challenge.owned',
                'not-acme',
            ],
            sorted([r.name for r in got.records]),
        )
