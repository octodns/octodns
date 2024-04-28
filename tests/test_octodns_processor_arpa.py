#
#
#

from unittest import TestCase

from octodns.processor.arpa import AutoArpa
from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.zone import Zone


class TestAutoArpa(TestCase):
    def test_empty_zone(self):
        # empty zone no records
        zone = Zone('unit.tests.', [])
        aa = AutoArpa('auto-arpa')
        aa.process_source_zone(zone, [])
        self.assertFalse(aa._records)

    def test_single_value_A(self):
        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone, 'a', {'ttl': 32, 'type': 'A', 'value': '1.2.3.4'}
        )
        zone.add_record(record)
        aa = AutoArpa('auto-arpa')
        aa.process_source_zone(zone, [])
        self.assertEqual(
            {'4.3.2.1.in-addr.arpa.': [(999, 3600, 'a.unit.tests.')]},
            aa._records,
        )

        # matching zone
        arpa = Zone('3.2.1.in-addr.arpa.', [])
        aa.populate(arpa)
        self.assertEqual(1, len(arpa.records))
        (ptr,) = arpa.records
        self.assertEqual('4.3.2.1.in-addr.arpa.', ptr.fqdn)
        self.assertEqual(record.fqdn, ptr.value)
        self.assertEqual(3600, ptr.ttl)

        # other zone
        arpa = Zone('4.4.4.in-addr.arpa.', [])
        aa.populate(arpa)
        self.assertEqual(0, len(arpa.records))

    def test_multi_value_A(self):
        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone,
            'a',
            {'ttl': 32, 'type': 'A', 'values': ['1.2.3.4', '1.2.3.5']},
        )
        zone.add_record(record)
        aa = AutoArpa('auto-arpa', ttl=1600)
        aa.process_source_zone(zone, [])
        self.assertEqual(
            {
                '4.3.2.1.in-addr.arpa.': [(999, 1600, 'a.unit.tests.')],
                '5.3.2.1.in-addr.arpa.': [(999, 1600, 'a.unit.tests.')],
            },
            aa._records,
        )

        arpa = Zone('3.2.1.in-addr.arpa.', [])
        aa.populate(arpa)
        self.assertEqual(2, len(arpa.records))
        ptr_1, ptr_2 = sorted(arpa.records)
        self.assertEqual('4.3.2.1.in-addr.arpa.', ptr_1.fqdn)
        self.assertEqual(record.fqdn, ptr_1.value)
        self.assertEqual('5.3.2.1.in-addr.arpa.', ptr_2.fqdn)
        self.assertEqual(record.fqdn, ptr_2.value)
        self.assertEqual(1600, ptr_2.ttl)

    def test_AAAA(self):
        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone, 'aaaa', {'ttl': 32, 'type': 'AAAA', 'value': 'ff:0c::4:2'}
        )
        zone.add_record(record)
        aa = AutoArpa('auto-arpa')
        aa.process_source_zone(zone, [])
        ip6_arpa = '2.0.0.0.4.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.c.0.0.0.f.f.0.0.ip6.arpa.'
        self.assertEqual(
            {ip6_arpa: [(999, 3600, 'aaaa.unit.tests.')]}, aa._records
        )

        # matching zone
        arpa = Zone('c.0.0.0.f.f.0.0.ip6.arpa.', [])
        aa.populate(arpa)
        self.assertEqual(1, len(arpa.records))
        (ptr,) = arpa.records
        self.assertEqual(ip6_arpa, ptr.fqdn)
        self.assertEqual(record.fqdn, ptr.value)

        # other zone
        arpa = Zone('c.0.0.0.e.f.0.0.ip6.arpa.', [])
        aa.populate(arpa)
        self.assertEqual(0, len(arpa.records))

    def test_geo(self):
        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone,
            'geo',
            {
                'ttl': 32,
                'type': 'A',
                'values': ['1.2.3.4', '1.2.3.5'],
                'geo': {
                    'AF': ['1.1.1.1'],
                    'AS-JP': ['2.2.2.2', '3.3.3.3'],
                    'NA-US': ['4.4.4.4', '5.5.5.5'],
                },
            },
        )
        zone.add_record(record)
        aa = AutoArpa('auto-arpa')
        aa.process_source_zone(zone, [])
        self.assertEqual(
            {
                '4.3.2.1.in-addr.arpa.': [(999, 3600, 'geo.unit.tests.')],
                '5.3.2.1.in-addr.arpa.': [(999, 3600, 'geo.unit.tests.')],
                '1.1.1.1.in-addr.arpa.': [(999, 3600, 'geo.unit.tests.')],
                '2.2.2.2.in-addr.arpa.': [(999, 3600, 'geo.unit.tests.')],
                '3.3.3.3.in-addr.arpa.': [(999, 3600, 'geo.unit.tests.')],
                '4.4.4.4.in-addr.arpa.': [(999, 3600, 'geo.unit.tests.')],
                '5.5.5.5.in-addr.arpa.': [(999, 3600, 'geo.unit.tests.')],
            },
            aa._records,
        )

    def test_dynamic(self):
        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone,
            'dynamic',
            {
                'ttl': 32,
                'type': 'A',
                'values': ['1.2.3.4', '1.2.3.5'],
                'dynamic': {
                    'pools': {
                        'one': {'values': [{'weight': 1, 'value': '3.3.3.3'}]},
                        'two': {
                            # Testing out of order value sorting here
                            'values': [
                                {'value': '5.5.5.5'},
                                {'value': '4.4.4.4'},
                            ]
                        },
                        'three': {
                            'values': [
                                {'weight': 10, 'value': '4.4.4.4'},
                                {'weight': 12, 'value': '5.5.5.5'},
                            ]
                        },
                    },
                    'rules': [
                        {'geos': ['AF', 'EU'], 'pool': 'three'},
                        {'geos': ['NA-US-CA'], 'pool': 'two'},
                        {'pool': 'one'},
                    ],
                },
            },
        )
        zone.add_record(record)
        aa = AutoArpa('auto-arpa')
        aa.process_source_zone(zone, [])
        zones = [
            '4.3.2.1.in-addr.arpa.',
            '5.3.2.1.in-addr.arpa.',
            '3.3.3.3.in-addr.arpa.',
            '4.4.4.4.in-addr.arpa.',
            '5.5.5.5.in-addr.arpa.',
        ]
        for zone in zones:
            unique_values = aa._order_and_unique_fqdns(
                aa._records[f'{zone}'], 999
            )
            self.assertEqual([(3600, 'dynamic.unit.tests.')], unique_values)

    def test_multiple_names(self):
        zone = Zone('unit.tests.', [])
        record1 = Record.new(
            zone, 'a1', {'ttl': 32, 'type': 'A', 'value': '1.2.3.4'}
        )
        zone.add_record(record1)
        record2 = Record.new(
            zone, 'a2', {'ttl': 32, 'type': 'A', 'value': '1.2.3.4'}
        )
        zone.add_record(record2)
        aa = AutoArpa('auto-arpa')
        aa.process_source_zone(zone, [])
        sorted_records = sorted(aa._records['4.3.2.1.in-addr.arpa.'])
        self.assertEqual(
            {
                '4.3.2.1.in-addr.arpa.': [
                    (999, 3600, 'a1.unit.tests.'),
                    (999, 3600, 'a2.unit.tests.'),
                ]
            },
            {'4.3.2.1.in-addr.arpa.': sorted_records},
        )

        # matching zone
        arpa = Zone('3.2.1.in-addr.arpa.', [])
        aa.populate(arpa)
        self.assertEqual(1, len(arpa.records))
        (ptr,) = arpa.records
        self.assertEqual('4.3.2.1.in-addr.arpa.', ptr.fqdn)
        self.assertEqual([record1.fqdn, record2.fqdn], ptr.values)
        self.assertEqual(3600, ptr.ttl)

    def test_address_boundaries(self):
        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone, 'a', {'ttl': 32, 'type': 'A', 'value': '10.20.3.4'}
        )
        zone.add_record(record)
        aa = AutoArpa('auto-arpa')
        aa.process_source_zone(zone, [])
        self.assertEqual(
            {'4.3.20.10.in-addr.arpa.': [(999, 3600, 'a.unit.tests.')]},
            aa._records,
        )

        # matching zone
        arpa = Zone('20.10.in-addr.arpa.', [])
        aa.populate(arpa)
        self.assertEqual(1, len(arpa.records))
        (ptr,) = arpa.records
        self.assertEqual('4.3.20.10.in-addr.arpa.', ptr.fqdn)
        self.assertEqual(record.fqdn, ptr.value)
        self.assertEqual(3600, ptr.ttl)

        # non-matching boundary edge case
        arpa = Zone('0.10.in-addr.arpa.', [])
        aa.populate(arpa)
        self.assertEqual(0, len(arpa.records))

    def test_single_value_A_with_space(self):
        zone = Zone('unit.tests.', [])

        # invalid record without lenient
        with self.assertRaises(ValidationError):
            Record.new(
                zone,
                'a with spaces',
                {'ttl': 32, 'type': 'A', 'value': '1.2.3.4'},
            )

        # invalid record with lenient
        lenient = True
        record = Record.new(
            zone,
            'a with spaces',
            {'ttl': 32, 'type': 'A', 'value': '1.2.3.4'},
            lenient=lenient,
        )
        zone.add_record(record)
        aa = AutoArpa('auto-arpa')
        aa.process_source_zone(zone, [])
        self.assertEqual(
            {
                '4.3.2.1.in-addr.arpa.': [
                    (999, 3600, 'a with spaces.unit.tests.')
                ]
            },
            aa._records,
        )

        # matching zone
        arpa = Zone('3.2.1.in-addr.arpa.', [])
        aa.populate(arpa, lenient=lenient)
        self.assertEqual(1, len(arpa.records))
        (ptr,) = arpa.records
        self.assertEqual('4.3.2.1.in-addr.arpa.', ptr.fqdn)
        self.assertEqual(record.fqdn, ptr.value)
        self.assertEqual(3600, ptr.ttl)

    def test_arpa_priority(self):
        aa = AutoArpa('auto-arpa')

        duplicate_values = [
            (999, 3600, 'a.unit.tests.'),
            (1, 3600, 'a.unit.tests.'),
        ]
        self.assertEqual(
            [(3600, 'a.unit.tests.')],
            aa._order_and_unique_fqdns(duplicate_values, max_auto_arpa=999),
        )

        duplicate_values = [
            (50, 3600, 'd.unit.tests.'),
            (999, 3600, 'dup.unit.tests.'),
            (3, 3600, 'a.unit.tests.'),
            (1, 3600, 'dup.unit.tests.'),
            (2, 3600, 'c.unit.tests.'),
        ]
        self.assertEqual(
            [
                (3600, 'dup.unit.tests.'),
                (3600, 'c.unit.tests.'),
                (3600, 'a.unit.tests.'),
                (3600, 'd.unit.tests.'),
            ],
            aa._order_and_unique_fqdns(duplicate_values, max_auto_arpa=999),
        )

        duplicate_values_2 = [
            (999, 3600, 'a.unit.tests.'),
            (999, 3600, 'a.unit.tests.'),
        ]
        self.assertEqual(
            [(3600, 'a.unit.tests.')],
            aa._order_and_unique_fqdns(duplicate_values_2, max_auto_arpa=999),
        )

        ordered_values = [
            (999, 3600, 'a.unit.tests.'),
            (1, 3600, 'b.unit.tests.'),
        ]
        self.assertEqual(
            [(3600, 'b.unit.tests.'), (3600, 'a.unit.tests.')],
            aa._order_and_unique_fqdns(ordered_values, max_auto_arpa=999),
        )

        max_one_value = [
            (999, 3600, 'a.unit.tests.'),
            (1, 3600, 'b.unit.tests.'),
        ]
        self.assertEqual(
            [(3600, 'b.unit.tests.')],
            aa._order_and_unique_fqdns(max_one_value, max_auto_arpa=1),
        )

    def test_arpa_inherit_ttl(self):
        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone, 'a1', {'ttl': 32, 'type': 'A', 'value': '1.2.3.4'}
        )
        zone.add_record(record)

        record2 = Record.new(
            zone,
            'a2',
            {
                'ttl': 64,
                'type': 'A',
                'value': '1.2.3.4',
                'octodns': {'auto_arpa_priority': 1},
            },
        )
        zone.add_record(record2)

        record3 = Record.new(
            zone, 'a3', {'ttl': 128, 'type': 'A', 'value': '1.2.3.4'}
        )
        zone.add_record(record3)

        aa = AutoArpa('auto-arpa', 3600, False, 999, True)
        aa.process_source_zone(zone, [])

        arpa = Zone('3.2.1.in-addr.arpa.', [])
        aa.populate(arpa)
        (ptr,) = arpa.records
        self.assertEqual(64, ptr.ttl)
