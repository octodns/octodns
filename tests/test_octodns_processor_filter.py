#
#
#

from unittest import TestCase

from octodns.processor.filter import (
    ExcludeRootNsChanges,
    IgnoreRootNsFilter,
    NameAllowlistFilter,
    NameRejectlistFilter,
    NetworkValueAllowlistFilter,
    NetworkValueRejectlistFilter,
    TypeAllowlistFilter,
    TypeRejectlistFilter,
    ValueAllowlistFilter,
    ValueRejectlistFilter,
    ZoneNameFilter,
)
from octodns.provider.plan import Plan
from octodns.record import Record, Update
from octodns.record.exception import ValidationError
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

    def test_include_target(self):
        filter_txt = TypeAllowlistFilter(
            'only-txt', ['TXT'], include_target=False
        )

        # as a source we don't see them
        got = filter_txt.process_source_zone(zone.copy())
        self.assertEqual(['txt', 'txt2'], sorted([r.name for r in got.records]))

        # but as a target we do b/c it's not included
        got = filter_txt.process_target_zone(zone.copy())
        self.assertEqual(
            ['a', 'a2', 'aaaa', 'txt', 'txt2'],
            sorted([r.name for r in got.records]),
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


class TestValueAllowListFilter(TestCase):
    zone = Zone('unit.tests.', [])
    matches = Record.new(
        zone,
        'good.exact',
        {'type': 'CNAME', 'ttl': 42, 'value': 'matches.example.com.'},
    )
    zone.add_record(matches)
    doesnt = Record.new(
        zone,
        'bad.exact',
        {'type': 'CNAME', 'ttl': 42, 'value': 'doesnt.example.com.'},
    )
    zone.add_record(doesnt)
    matches_many = Record.new(
        zone,
        'good.values',
        {
            'type': 'TXT',
            'ttl': 42,
            'values': ['matches.example.com.', 'another'],
        },
    )
    zone.add_record(matches_many)
    doesnt_many = Record.new(
        zone,
        'bad.values',
        {
            'type': 'TXT',
            'ttl': 42,
            'values': ['doesnt.example.com.', 'another'],
        },
    )
    zone.add_record(doesnt_many)
    matchable1 = Record.new(
        zone,
        'first.regex',
        {'type': 'CNAME', 'ttl': 42, 'value': 'start.f43ad96.end.'},
    )
    zone.add_record(matchable1)
    matchable2 = Record.new(
        zone,
        'second.regex',
        {'type': 'CNAME', 'ttl': 42, 'value': 'start.a3b444c.end.'},
    )
    zone.add_record(matchable2)

    def test_exact(self):
        allows = ValueAllowlistFilter('exact', ('matches.example.com.',))

        self.assertEqual(6, len(self.zone.records))
        filtered = allows.process_source_zone(self.zone.copy())
        self.assertEqual(2, len(filtered.records))
        self.assertEqual(
            ['good.exact', 'good.values'],
            sorted([r.name for r in filtered.records]),
        )

    def test_regex(self):
        allows = ValueAllowlistFilter('exact', ('/^start\\..+\\.end\\.$/',))

        self.assertEqual(6, len(self.zone.records))
        filtered = allows.process_source_zone(self.zone.copy())
        self.assertEqual(2, len(filtered.records))
        self.assertEqual(
            ['first.regex', 'second.regex'],
            sorted([r.name for r in filtered.records]),
        )


class TestValueRejectListFilter(TestCase):
    zone = Zone('unit.tests.', [])
    matches = Record.new(
        zone,
        'good.compare',
        {'type': 'CNAME', 'ttl': 42, 'value': 'matches.example.com.'},
    )
    zone.add_record(matches)
    doesnt = Record.new(
        zone,
        'bad.compare',
        {'type': 'CNAME', 'ttl': 42, 'value': 'doesnt.example.com.'},
    )
    zone.add_record(doesnt)
    matches_many = Record.new(
        zone,
        'good.values',
        {
            'type': 'TXT',
            'ttl': 42,
            'values': ['matches.example.com.', 'another'],
        },
    )
    zone.add_record(matches_many)
    doesnt_many = Record.new(
        zone,
        'bad.values',
        {
            'type': 'TXT',
            'ttl': 42,
            'values': ['doesnt.example.com.', 'another'],
        },
    )
    zone.add_record(doesnt_many)
    matchable1 = Record.new(
        zone,
        'first.regex',
        {'type': 'CNAME', 'ttl': 42, 'value': 'start.f43ad96.end.'},
    )
    zone.add_record(matchable1)
    matchable2 = Record.new(
        zone,
        'second.regex',
        {'type': 'CNAME', 'ttl': 42, 'value': 'start.a3b444c.end.'},
    )
    zone.add_record(matchable2)

    def test_exact(self):
        rejects = ValueRejectlistFilter('exact', ('matches.example.com.',))

        self.assertEqual(6, len(self.zone.records))
        filtered = rejects.process_source_zone(self.zone.copy())
        self.assertEqual(4, len(filtered.records))
        self.assertEqual(
            ['bad.compare', 'bad.values', 'first.regex', 'second.regex'],
            sorted([r.name for r in filtered.records]),
        )

    def test_regex(self):
        rejects = ValueRejectlistFilter('exact', ('/^start\\..+\\.end\\.$/',))

        self.assertEqual(6, len(self.zone.records))
        filtered = rejects.process_source_zone(self.zone.copy())
        self.assertEqual(4, len(filtered.records))
        self.assertEqual(
            ['bad.compare', 'bad.values', 'good.compare', 'good.values'],
            sorted([r.name for r in filtered.records]),
        )


class TestNetworkValueFilter(TestCase):
    zone = Zone('unit.tests.', [])
    for record in [
        Record.new(
            zone,
            'private-ipv4',
            {'type': 'A', 'ttl': 42, 'value': '10.42.42.42'},
        ),
        Record.new(
            zone,
            'public-ipv4',
            {'type': 'A', 'ttl': 42, 'value': '42.42.42.42'},
        ),
        Record.new(
            zone,
            'private-ipv6',
            {'type': 'AAAA', 'ttl': 42, 'value': 'fd12:3456:789a:1::1'},
        ),
        Record.new(
            zone,
            'public-ipv6',
            {'type': 'AAAA', 'ttl': 42, 'value': 'dead:beef:cafe::1'},
        ),
        Record.new(
            zone,
            'keep-me',
            {'ttl': 30, 'type': 'TXT', 'value': 'this should always be here'},
        ),
    ]:
        zone.add_record(record)

    def test_bad_config(self):
        with self.assertRaises(ValueError):
            NetworkValueRejectlistFilter(
                'rejectlist', set(('string', '42.42.42.42/43'))
            )

    def test_reject(self):
        filter_private = NetworkValueRejectlistFilter(
            'rejectlist', set(('10.0.0.0/8', 'fd00::/8'))
        )

        got = filter_private.process_source_zone(self.zone.copy())
        self.assertEqual(
            ['keep-me', 'public-ipv4', 'public-ipv6'],
            sorted([r.name for r in got.records]),
        )

    def test_allow(self):
        filter_private = NetworkValueAllowlistFilter(
            'allowlist', set(('10.0.0.0/8', 'fd00::/8'))
        )

        got = filter_private.process_source_zone(self.zone.copy())
        self.assertEqual(
            ['keep-me', 'private-ipv4', 'private-ipv6'],
            sorted([r.name for r in got.records]),
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


class TestExcludeRootNsChanges(TestCase):
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
    changes_with_root = [
        Update(root, root),
        Update(not_root, not_root),
        Update(not_ns, not_ns),
    ]
    plan_with_root = Plan(zone, zone, changes_with_root, True)
    changes_without_root = [Update(not_root, not_root), Update(not_ns, not_ns)]
    plan_without_root = Plan(zone, zone, changes_without_root, True)

    def test_no_plan(self):
        proc = ExcludeRootNsChanges('exclude-root')
        self.assertFalse(proc.process_plan(None, None, None))

    def test_error(self):
        proc = ExcludeRootNsChanges('exclude-root')

        with self.assertRaises(ValidationError) as ctx:
            proc.process_plan(self.plan_with_root, None, None)
        self.assertEqual(
            ['root NS changes are disallowed'], ctx.exception.reasons
        )

        self.assertEqual(
            self.plan_without_root,
            proc.process_plan(self.plan_without_root, None, None),
        )

    def test_warning(self):
        proc = ExcludeRootNsChanges('exclude-root', error=False)

        filtered_plan = proc.process_plan(self.plan_with_root, None, None)
        self.assertEqual(self.plan_without_root.changes, filtered_plan.changes)

        self.assertEqual(
            self.plan_without_root,
            proc.process_plan(self.plan_without_root, None, None),
        )


class TestZoneNameFilter(TestCase):
    def test_ends_with_zone(self):
        zone_name_filter = ZoneNameFilter('zone-name', error=False)

        zone = Zone('unit.tests.', [])

        # something that doesn't come into play
        zone.add_record(
            Record.new(
                zone, 'www', {'type': 'A', 'ttl': 43, 'value': '1.2.3.4'}
            )
        )

        # something that has the zone name, but doesn't end with it
        zone.add_record(
            Record.new(
                zone,
                f'{zone.name}more',
                {'type': 'A', 'ttl': 43, 'value': '1.2.3.4'},
            )
        )

        self.assertEqual(2, len(zone.records))
        filtered = zone_name_filter.process_source_zone(zone.copy())
        # get everything back
        self.assertEqual(2, len(filtered.records))

        with_dot = zone.copy()
        with_dot.add_record(
            Record.new(
                zone, zone.name, {'type': 'A', 'ttl': 43, 'value': '1.2.3.4'}
            )
        )
        self.assertEqual(3, len(with_dot.records))
        filtered = zone_name_filter.process_source_zone(with_dot.copy())
        # don't get the one that ends with the zone name
        self.assertEqual(2, len(filtered.records))

        without_dot = zone.copy()
        without_dot.add_record(
            Record.new(
                zone,
                zone.name[:-1],
                {'type': 'A', 'ttl': 43, 'value': '1.2.3.4'},
            )
        )
        self.assertEqual(3, len(without_dot.records))
        filtered = zone_name_filter.process_source_zone(without_dot.copy())
        # don't get the one that ends with the zone name
        self.assertEqual(2, len(filtered.records))

    def test_error(self):
        errors = ZoneNameFilter('zone-name', error=True)

        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(
                zone, zone.name, {'type': 'A', 'ttl': 43, 'value': '1.2.3.4'}
            )
        )
        with self.assertRaises(ValidationError) as ctx:
            errors.process_source_zone(zone)
        self.assertEqual(
            ['record name ends with zone name'], ctx.exception.reasons
        )
