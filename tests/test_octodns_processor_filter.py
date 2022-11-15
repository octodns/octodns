#
#
#

from unittest import TestCase

from octodns.processor.filter import (
    IgnoreRootNsFilter,
    NameAllowlistFilter,
    NameRejectlistFilter,
    TypeAllowlistFilter,
    TypeRejectlistFilter,
)
from octodns.record import Record
from octodns.zone import Zone

zone = Zone('unit.tests.', [])
for record in [
    Record.new(zone, 'a', {'ttl': 30, 'type': 'A', 'value': '1.2.3.4'}),
    Record.new(zone, 'aaaa', {'ttl': 30, 'type': 'AAAA', 'value': '::1'}),
    Record.new(
        zone, 'txt', {'ttl': 30, 'type': 'TXT', 'value': 'Hello World!'}
    ),
    Record.new(zone, 'a2', {'ttl': 30, 'type': 'A', 'value': '2.3.4.5'}),
    Record.new(
        zone, 'txt2', {'ttl': 30, 'type': 'TXT', 'value': 'That will do'}
    ),
]:
    zone.add_record(record)


class TestTypeAllowListFilter(TestCase):
    def test_basics(self):
        filter_a = TypeAllowlistFilter('only-a', set(('A')))

        got = filter_a.process_source_zone(zone.copy())
        self.assertEqual(['a', 'a2'], sorted([r.name for r in got.records]))

        filter_aaaa = TypeAllowlistFilter('only-aaaa', ('AAAA',))
        got = filter_aaaa.process_source_zone(zone.copy())
        self.assertEqual(['aaaa'], sorted([r.name for r in got.records]))

        filter_txt = TypeAllowlistFilter('only-txt', ['TXT'])
        got = filter_txt.process_target_zone(zone.copy())
        self.assertEqual(['txt', 'txt2'], sorted([r.name for r in got.records]))

        filter_a_aaaa = TypeAllowlistFilter('only-aaaa', set(('A', 'AAAA')))
        got = filter_a_aaaa.process_target_zone(zone.copy())
        self.assertEqual(
            ['a', 'a2', 'aaaa'], sorted([r.name for r in got.records])
        )


class TestTypeRejectListFilter(TestCase):
    def test_basics(self):
        filter_a = TypeRejectlistFilter('not-a', set(('A')))

        got = filter_a.process_source_zone(zone.copy())
        self.assertEqual(
            ['aaaa', 'txt', 'txt2'], sorted([r.name for r in got.records])
        )

        filter_aaaa = TypeRejectlistFilter('not-aaaa', ('AAAA',))
        got = filter_aaaa.process_source_zone(zone.copy())
        self.assertEqual(
            ['a', 'a2', 'txt', 'txt2'], sorted([r.name for r in got.records])
        )

        filter_txt = TypeRejectlistFilter('not-txt', ['TXT'])
        got = filter_txt.process_target_zone(zone.copy())
        self.assertEqual(
            ['a', 'a2', 'aaaa'], sorted([r.name for r in got.records])
        )

        filter_a_aaaa = TypeRejectlistFilter('not-a-aaaa', set(('A', 'AAAA')))
        got = filter_a_aaaa.process_target_zone(zone.copy())
        self.assertEqual(['txt', 'txt2'], sorted([r.name for r in got.records]))


class TestNameAllowListFilter(TestCase):
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

    def test_exact(self):
        allows = NameAllowlistFilter('exact', ('matches',))

        self.assertEqual(4, len(self.zone.records))
        filtered = allows.process_source_zone(self.zone.copy())
        self.assertEqual(1, len(filtered.records))
        self.assertEqual(['matches'], [r.name for r in filtered.records])

    def test_regex(self):
        allows = NameAllowlistFilter('exact', ('/^start-.+-end$/',))

        self.assertEqual(4, len(self.zone.records))
        filtered = allows.process_source_zone(self.zone.copy())
        self.assertEqual(2, len(filtered.records))
        self.assertEqual(
            ['start-a3b444c-end', 'start-f43ad96-end'],
            sorted([r.name for r in filtered.records]),
        )


class TestNameRejectListFilter(TestCase):
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

    def test_exact(self):
        rejects = NameRejectlistFilter('exact', ('matches',))

        self.assertEqual(4, len(self.zone.records))
        filtered = rejects.process_source_zone(self.zone.copy())
        self.assertEqual(3, len(filtered.records))
        self.assertEqual(
            ['doesnt', 'start-a3b444c-end', 'start-f43ad96-end'],
            sorted([r.name for r in filtered.records]),
        )

    def test_regex(self):
        rejects = NameRejectlistFilter('exact', ('/^start-.+-end$/',))

        self.assertEqual(4, len(self.zone.records))
        filtered = rejects.process_source_zone(self.zone.copy())
        self.assertEqual(2, len(filtered.records))
        self.assertEqual(
            ['doesnt', 'matches'], sorted([r.name for r in filtered.records])
        )


class TestIgnoreRootNsFilter(TestCase):
    zone = Zone('unit.tests.', [])
    root = Record.new(
        zone, '', {'type': 'NS', 'ttl': 42, 'value': 'ns1.unit.tests.'}
    )
    zone.add_record(root)
    not_root = Record.new(
        zone, 'sub', {'type': 'NS', 'ttl': 43, 'value': 'ns2.unit.tests.'}
    )
    zone.add_record(not_root)
    not_ns = Record.new(zone, '', {'type': 'A', 'ttl': 42, 'value': '3.4.5.6'})
    zone.add_record(not_ns)

    def test_filtering(self):
        proc = IgnoreRootNsFilter('no-root')

        self.assertEqual(3, len(self.zone.records))
        filtered = proc.process_source_zone(self.zone.copy())
        self.assertEqual(2, len(filtered.records))
        self.assertEqual(
            [('A', ''), ('NS', 'sub')],
            sorted([(r._type, r.name) for r in filtered.records]),
        )
