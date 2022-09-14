from unittest import TestCase

from octodns.processor.restrict import (
    RestrictionException,
    TtlRestrictionFilter,
)
from octodns.record import Record
from octodns.zone import Zone


class TestTtlRestrictionFilter(TestCase):
    def test_restrict_ttl(self):
        # configured values
        restrictor = TtlRestrictionFilter('test', min_ttl=32, max_ttl=1024)

        zone = Zone('unit.tests.', [])
        good = Record.new(
            zone, 'good', {'type': 'A', 'ttl': 42, 'value': '1.2.3.4'}
        )
        zone.add_record(good)

        restricted = restrictor.process_source_zone(zone)
        self.assertEqual(zone.records, restricted.records)

        # too low
        low = Record.new(
            zone, 'low', {'type': 'A', 'ttl': 16, 'value': '1.2.3.4'}
        )
        copy = zone.copy()
        copy.add_record(low)
        with self.assertRaises(RestrictionException) as ctx:
            restrictor.process_source_zone(copy)
        self.assertEqual(
            'low.unit.tests. ttl=16 too low, min_ttl=32', str(ctx.exception)
        )

        # with lenient set, we can go lower
        lenient = Record.new(
            zone,
            'low',
            {
                'octodns': {'lenient': True},
                'type': 'A',
                'ttl': 16,
                'value': '1.2.3.4',
            },
        )
        copy = zone.copy()
        copy.add_record(lenient)
        restricted = restrictor.process_source_zone(copy)
        self.assertEqual(copy.records, restricted.records)

        # too high
        high = Record.new(
            zone, 'high', {'type': 'A', 'ttl': 2048, 'value': '1.2.3.4'}
        )
        copy = zone.copy()
        copy.add_record(high)
        with self.assertRaises(RestrictionException) as ctx:
            restrictor.process_source_zone(copy)
        self.assertEqual(
            'high.unit.tests. ttl=2048 too high, max_ttl=1024',
            str(ctx.exception),
        )

        # too low defaults
        restrictor = TtlRestrictionFilter('test')
        low = Record.new(
            zone, 'low', {'type': 'A', 'ttl': 0, 'value': '1.2.3.4'}
        )
        copy = zone.copy()
        copy.add_record(low)
        with self.assertRaises(RestrictionException) as ctx:
            restrictor.process_source_zone(copy)
        self.assertEqual(
            'low.unit.tests. ttl=0 too low, min_ttl=1', str(ctx.exception)
        )

        # too high defaults
        high = Record.new(
            zone, 'high', {'type': 'A', 'ttl': 999999, 'value': '1.2.3.4'}
        )
        copy = zone.copy()
        copy.add_record(high)
        with self.assertRaises(RestrictionException) as ctx:
            restrictor.process_source_zone(copy)
        self.assertEqual(
            'high.unit.tests. ttl=999999 too high, max_ttl=604800',
            str(ctx.exception),
        )

        # allowed_ttls
        restrictor = TtlRestrictionFilter('test', allowed_ttls=[42, 300])

        # add 300 (42 is already there)
        another = Record.new(
            zone, 'another', {'type': 'A', 'ttl': 300, 'value': '4.5.6.7'}
        )
        zone.add_record(another)

        # 42 and 300 are allowed through
        restricted = restrictor.process_source_zone(zone)
        self.assertEqual(zone.records, restricted.records)

        # 16 is not
        copy = zone.copy()
        copy.add_record(low)
        with self.assertRaises(RestrictionException) as ctx:
            restrictor.process_source_zone(copy)
        self.assertEqual(
            'low.unit.tests. ttl=0 not an allowed value, allowed_ttls={42, 300}',
            str(ctx.exception),
        )
