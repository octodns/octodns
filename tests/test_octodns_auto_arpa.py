#
#
#

from unittest import TestCase

from octodns.auto_arpa import AutoArpa
from octodns.record import Record
from octodns.zone import Zone


class TestAutoArpa(TestCase):
    def test_v4(self):
        aa = AutoArpa()

        # a record it won't be interested in b/c of type
        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone, 'ns', {'type': 'NS', 'ttl': 1800, 'value': 'ns1.unit.tests.'}
        )
        zone.add_record(record)
        aa.process_source_zone(zone, [])
        # nothing recorded
        self.assertFalse(aa._addrs)

        # a record it will record
        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone, 'a', {'type': 'A', 'ttl': 1800, 'value': '10.0.0.1'}
        )
        zone.add_record(record)
        aa.process_source_zone(zone, [])
        self.assertEqual(
            {'1.0.0.10.in-addr.arpa.': ['a.unit.tests.']}, dict(aa._addrs)
        )

        # another record it will record
        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone, 'b', {'type': 'A', 'ttl': 1800, 'value': '10.0.42.1'}
        )
        zone.add_record(record)
        aa.process_source_zone(zone, [])
        self.assertEqual(
            {
                '1.0.0.10.in-addr.arpa.': ['a.unit.tests.'],
                '1.42.0.10.in-addr.arpa.': ['b.unit.tests.'],
            },
            dict(aa._addrs),
        )

        # a second record pointed to the same IP
        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone, 'c', {'type': 'A', 'ttl': 1800, 'value': '10.0.42.1'}
        )
        zone.add_record(record)
        aa.process_source_zone(zone, [])
        self.assertEqual(
            {
                '1.0.0.10.in-addr.arpa.': ['a.unit.tests.'],
                '1.42.0.10.in-addr.arpa.': ['b.unit.tests.', 'c.unit.tests.'],
            },
            dict(aa._addrs),
        )

        # subnet with just 1 record
        zone = Zone('0.0.10.in-addr.arpa.', [])
        aa.populate(zone)
        self.assertEqual(
            {'1.0.0.10.in-addr.arpa.': ['a.unit.tests.']},
            {r.fqdn: r.values for r in zone.records},
        )

        # subnet with 2 records
        zone = Zone('0.10.in-addr.arpa.', [])
        aa.populate(zone)
        self.assertEqual(
            {
                '1.0.0.10.in-addr.arpa.': ['a.unit.tests.'],
                '1.42.0.10.in-addr.arpa.': ['b.unit.tests.', 'c.unit.tests.'],
            },
            {r.fqdn: r.values for r in zone.records},
        )

    def test_v6(self):
        aa = AutoArpa()

        # a v6 record it will record
        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone, 'aaaa', {'type': 'AAAA', 'ttl': 1800, 'value': 'fc00::1'}
        )
        zone.add_record(record)
        aa.process_source_zone(zone, [])
        self.assertEqual(
            {
                '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.c.f.ip6.arpa.': [
                    'aaaa.unit.tests.'
                ]
            },
            dict(aa._addrs),
        )

        # another v6 record it will record
        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone, 'bbbb', {'type': 'AAAA', 'ttl': 1800, 'value': 'fc42::1'}
        )
        zone.add_record(record)
        aa.process_source_zone(zone, [])
        self.assertEqual(
            {
                '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.c.f.ip6.arpa.': [
                    'aaaa.unit.tests.'
                ],
                '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.2.4.c.f.ip6.arpa.': [
                    'bbbb.unit.tests.'
                ],
            },
            dict(aa._addrs),
        )

        # subnet with just 1 record
        zone = Zone('0.0.c.f.ip6.arpa.', [])
        aa.populate(zone)
        self.assertEqual(
            {
                '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.c.f.ip6.arpa.': [
                    'aaaa.unit.tests.'
                ]
            },
            {r.fqdn: r.values for r in zone.records},
        )

        # subnet with 2 records
        zone = Zone('c.f.ip6.arpa.', [])
        aa.populate(zone)
        self.assertEqual(
            {
                '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.c.f.ip6.arpa.': [
                    'aaaa.unit.tests.'
                ],
                '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.2.4.c.f.ip6.arpa.': [
                    'bbbb.unit.tests.'
                ],
            },
            {r.fqdn: r.values for r in zone.records},
        )
