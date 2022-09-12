from unittest import TestCase

from octodns.processor.restrict import (
    RestrictionException,
    TtlRestrictionFilter,
)
from octodns.record import Record
from octodns.zone import Zone


class TestTtlRestrictionFilter(TestCase):
    zone = Zone('unit.tests.', [])
    matches = Record.new(
        zone, 'matches', {'type': 'A', 'ttl': 42, 'value': '1.2.3.4'}
    )
    zone.add_record(matches)
    doesnt = Record.new(
        zone, 'doesnt', {'type': 'A', 'ttl': 42, 'value': '2.3.4.5'}
    )
    zone.add_record(doesnt)
    matchable1 = Record.new(
        zone, 'start-f43ad96-end', {'type': 'A', 'ttl': 42, 'value': '3.4.5.6'}
    )
    zone.add_record(matchable1)
    matchable2 = Record.new(
        zone, 'start-a3b444c-end', {'type': 'A', 'ttl': 42, 'value': '4.5.6.7'}
    )
    zone.add_record(matchable2)

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

        # defaults
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
