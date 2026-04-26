#
#
#

from unittest import TestCase

from octodns.processor.subzone import SubzoneOverlapFilter
from octodns.record import Record
from octodns.zone import Zone


def _ptr(zone, name):
    record = Record.new(
        zone,
        name,
        {'type': 'PTR', 'ttl': 42, 'value': 'host.example.com.'},
        lenient=True,
    )
    zone.add_record(record, lenient=True)
    return record


class SubzoneOverlapFilterTest(TestCase):
    def test_no_sub_zones_is_passthrough(self):
        flt = SubzoneOverlapFilter('test')

        zone = Zone('10.in-addr.arpa.', [])
        _ptr(zone, '5.0.0')
        _ptr(zone, '5.0.1')

        got = flt.process_source_zone(zone, sources=[])

        self.assertIs(got, zone)
        self.assertEqual(
            {'5.0.0.10.in-addr.arpa.', '5.0.1.10.in-addr.arpa.'},
            {r.fqdn for r in got.records},
        )

    def test_strips_records_owned_by_sub_zone(self):
        flt = SubzoneOverlapFilter('test')

        # parent /8 with a /24 child at 1.10.in-addr.arpa., so sub_zones=['1']
        zone = Zone('10.in-addr.arpa.', ['1'])
        _ptr(zone, '5.0.1')  # 10.1.0.5 - drop, owned by sub-zone
        _ptr(zone, '99.99.1')  # 10.1.99.99 - drop
        _ptr(zone, '5.0.2')  # 10.2.0.5 - keep

        flt.process_source_zone(zone, sources=[])

        self.assertEqual(
            ['5.0.2.10.in-addr.arpa.'], [r.fqdn for r in zone.records]
        )

    def test_preserves_ns_at_sub_zone_boundary(self):
        flt = SubzoneOverlapFilter('test')

        # NS at the exact boundary is the delegation glue and must survive.
        zone = Zone('10.in-addr.arpa.', ['1'])
        ns = Record.new(
            zone,
            '1',
            {
                'type': 'NS',
                'ttl': 3600,
                'values': ['ns1.example.com.', 'ns2.example.com.'],
            },
        )
        zone.add_record(ns)
        _ptr(zone, '5.0.1')  # under the sub-zone, drop

        flt.process_source_zone(zone, sources=[])

        kept = sorted((r._type, r.fqdn) for r in zone.records)
        self.assertEqual([('NS', '1.10.in-addr.arpa.')], kept)

    def test_works_for_arbitrary_record_types(self):
        # The same overlap class can affect any record type, not just PTR.
        flt = SubzoneOverlapFilter('test')

        zone = Zone('example.com.', ['dev'])
        a = Record.new(
            zone,
            'host.dev',
            {'type': 'A', 'ttl': 60, 'value': '203.0.113.1'},
            lenient=True,
        )
        zone.add_record(a, lenient=True)
        keep = Record.new(
            zone, 'www', {'type': 'A', 'ttl': 60, 'value': '203.0.113.2'}
        )
        zone.add_record(keep)

        flt.process_source_zone(zone, sources=[])

        self.assertEqual(['www.example.com.'], [r.fqdn for r in zone.records])

    def test_sibling_label_does_not_match(self):
        # 11.in-addr.arpa. is not under sub_zone '1' - Zone.owns uses
        # dot-anchored matching, so this must not be stripped.
        flt = SubzoneOverlapFilter('test')

        zone = Zone('in-addr.arpa.', ['1'])
        _ptr(zone, '5.0.0.11')  # 11.0.0.5 - sibling, keep
        _ptr(zone, '5.0.0.1')  # 1.0.0.5 - in sub-zone, drop

        flt.process_source_zone(zone, sources=[])

        self.assertEqual(
            ['5.0.0.11.in-addr.arpa.'], [r.fqdn for r in zone.records]
        )

    def test_multi_label_sub_zone(self):
        # /16 parent (168.192.in-addr.arpa.) with /24 child
        # (1.168.192.in-addr.arpa.), so the relative sub-zone name is '1'.
        flt = SubzoneOverlapFilter('test')

        zone = Zone('168.192.in-addr.arpa.', ['1'])
        _ptr(zone, '5.1')  # 192.168.1.5 - drop
        _ptr(zone, '5.2')  # 192.168.2.5 - keep

        flt.process_source_zone(zone, sources=[])

        self.assertEqual(
            ['5.2.168.192.in-addr.arpa.'], [r.fqdn for r in zone.records]
        )

    def test_ipv6_sub_zone(self):
        # /32 parent with /48 child -- relative sub-zone is 'e.f.a.c'
        # (cafe in nibble form, reversed).
        flt = SubzoneOverlapFilter('test')

        zone = Zone('8.b.d.0.1.0.0.2.ip6.arpa.', ['e.f.a.c'])
        in_child = Record.new(
            zone,
            '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.e.f.a.c',
            {'type': 'PTR', 'ttl': 42, 'value': 'cafe.example.com.'},
            lenient=True,
        )
        zone.add_record(in_child, lenient=True)
        out = Record.new(
            zone,
            '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.f.e.e.b',
            {'type': 'PTR', 'ttl': 42, 'value': 'beef.example.com.'},
        )
        zone.add_record(out)

        flt.process_source_zone(zone, sources=[])

        self.assertEqual(
            [
                '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.f.e.e.b.'
                '8.b.d.0.1.0.0.2.ip6.arpa.'
            ],
            [r.fqdn for r in zone.records],
        )

    def test_multiple_sub_zones(self):
        flt = SubzoneOverlapFilter('test')

        zone = Zone('10.in-addr.arpa.', ['1', '2'])
        _ptr(zone, '5.0.1')  # in sub-zone 1, drop
        _ptr(zone, '5.0.2')  # in sub-zone 2, drop
        _ptr(zone, '5.0.3')  # neither, keep

        flt.process_source_zone(zone, sources=[])

        self.assertEqual(
            ['5.0.3.10.in-addr.arpa.'], [r.fqdn for r in zone.records]
        )

    def test_returns_same_zone_object(self):
        flt = SubzoneOverlapFilter('test')
        zone = Zone('10.in-addr.arpa.', ['1'])
        self.assertIs(zone, flt.process_source_zone(zone, sources=[]))

    def test_no_records_to_remove_skips_log(self):
        # When the parent has sub_zones but no overlapping records, the
        # info log is skipped. Exercises the `if removed:` false branch.
        flt = SubzoneOverlapFilter('test')

        zone = Zone('10.in-addr.arpa.', ['1'])
        _ptr(zone, '5.0.2')

        flt.process_source_zone(zone, sources=[])

        self.assertEqual(
            ['5.0.2.10.in-addr.arpa.'], [r.fqdn for r in zone.records]
        )
