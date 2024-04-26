#
#
#

from unittest import TestCase

from octodns.processor.trailing_dots import (
    EnsureTrailingDots,
    _ensure_trailing_dots,
    _no_trailing_dot,
)
from octodns.record import Record
from octodns.record.alias import AliasValue
from octodns.record.cname import CnameValue
from octodns.record.dname import DnameValue
from octodns.record.ns import NsValue
from octodns.record.ptr import PtrValue
from octodns.zone import Zone


def _find(zone, name):
    return next(r for r in zone.records if r.name == name)


class EnsureTrailingDotsTest(TestCase):
    def test_cname(self):
        etd = EnsureTrailingDots('test')

        zone = Zone('unit.tests.', [])
        has = Record.new(
            zone,
            'has',
            {'type': 'CNAME', 'ttl': 42, 'value': 'absolute.target.'},
        )
        zone.add_record(has)
        missing = Record.new(
            zone,
            'missing',
            {'type': 'CNAME', 'ttl': 42, 'value': 'relative.target'},
            lenient=True,
        )
        zone.add_record(missing)

        got = etd.process_source_zone(zone, None)

        self.assertEqual('absolute.target.', _find(got, 'has').value)
        self.assertEqual('relative.target.', _find(got, 'missing').value)
        # ensure types were preserved
        self.assertIsInstance(_find(got, 'has').value, CnameValue)
        self.assertIsInstance(_find(got, 'missing').value, CnameValue)

    def test_alias(self):
        etd = EnsureTrailingDots('test')

        zone = Zone('unit.tests.', [])
        has = Record.new(
            zone,
            'has',
            {'type': 'ALIAS', 'ttl': 42, 'value': 'absolute.target.'},
            lenient=True,
        )
        zone.add_record(has)
        missing = Record.new(
            zone,
            'missing',
            {'type': 'ALIAS', 'ttl': 42, 'value': 'relative.target'},
            lenient=True,
        )
        zone.add_record(missing)

        got = etd.process_source_zone(zone, None)
        self.assertEqual('absolute.target.', _find(got, 'has').value)
        self.assertEqual('relative.target.', _find(got, 'missing').value)
        self.assertIsInstance(_find(got, 'has').value, AliasValue)
        self.assertIsInstance(_find(got, 'missing').value, AliasValue)

    def test_dname(self):
        etd = EnsureTrailingDots('test')

        zone = Zone('unit.tests.', [])
        has = Record.new(
            zone,
            'has',
            {'type': 'DNAME', 'ttl': 42, 'value': 'absolute.target.'},
        )
        zone.add_record(has)
        missing = Record.new(
            zone,
            'missing',
            {'type': 'DNAME', 'ttl': 42, 'value': 'relative.target'},
            lenient=True,
        )
        zone.add_record(missing)

        got = etd.process_source_zone(zone, None)
        self.assertEqual('absolute.target.', _find(got, 'has').value)
        self.assertEqual('relative.target.', _find(got, 'missing').value)
        self.assertIsInstance(_find(got, 'has').value, DnameValue)
        self.assertIsInstance(_find(got, 'missing').value, DnameValue)

    def test_mx(self):
        etd = EnsureTrailingDots('test')

        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone,
            'record',
            {
                'type': 'MX',
                'ttl': 42,
                'values': [
                    {'preference': 1, 'exchange': 'absolute.target.'},
                    {'preference': 1, 'exchange': 'relative.target'},
                ],
            },
            lenient=True,
        )
        zone.add_record(record)

        # processor
        got = etd.process_source_zone(zone, None)
        got = next(iter(got.records))
        self.assertEqual(
            ['absolute.target.', 'relative.target.'],
            [v.exchange for v in got.values],
        )

        # specifically test the checker
        self.assertTrue(_no_trailing_dot(record, 'exchange'))
        # specifically test the fixer
        self.assertEqual(
            ['absolute.target.', 'relative.target.'],
            [
                v.exchange
                for v in _ensure_trailing_dots(record, 'exchange').values
            ],
        )
        # this time with nothing that matches
        record.values[1].exchange = 'also.absolute.'
        self.assertFalse(_no_trailing_dot(record, 'exchange'))

    def test_ns(self):
        etd = EnsureTrailingDots('test')

        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone,
            'record',
            {
                'type': 'NS',
                'ttl': 42,
                'values': ['absolute.target.', 'relative.target'],
            },
            lenient=True,
        )
        zone.add_record(record)

        got = etd.process_source_zone(zone, None)
        got = next(iter(got.records))
        self.assertEqual(['absolute.target.', 'relative.target.'], got.values)
        self.assertIsInstance(got.values[0], NsValue)
        self.assertIsInstance(got.values[1], NsValue)

        # again, but this time nothing to fix so that we fully use up the
        # generator
        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone,
            'record',
            {
                'type': 'NS',
                'ttl': 42,
                'values': ['absolute.target.', 'another.target.'],
            },
        )
        zone.add_record(record)

        got = etd.process_source_zone(zone, None)
        got = next(iter(got.records))
        self.assertEqual(['absolute.target.', 'another.target.'], got.values)

    def test_ptr(self):
        etd = EnsureTrailingDots('test')

        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone,
            'record',
            {
                'type': 'PTR',
                'ttl': 42,
                'values': ['absolute.target.', 'relative.target'],
            },
            lenient=True,
        )
        zone.add_record(record)

        got = etd.process_source_zone(zone, None)
        got = next(iter(got.records))
        self.assertEqual(['absolute.target.', 'relative.target.'], got.values)
        self.assertIsInstance(got.values[0], PtrValue)
        self.assertIsInstance(got.values[1], PtrValue)

    def test_srv(self):
        etd = EnsureTrailingDots('test')

        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone,
            'record',
            {
                'type': 'SRV',
                'ttl': 42,
                'values': [
                    {
                        'priority': 1,
                        'weight': 1,
                        'port': 99,
                        'target': 'absolute.target.',
                    },
                    {
                        'priority': 1,
                        'weight': 1,
                        'port': 99,
                        'target': 'relative.target',
                    },
                ],
            },
            lenient=True,
        )
        zone.add_record(record)

        # processor
        got = etd.process_source_zone(zone, None)
        got = next(iter(got.records))
        self.assertEqual(
            ['absolute.target.', 'relative.target.'],
            [v.target for v in got.values],
        )

        # specifically test the checker
        self.assertTrue(_no_trailing_dot(record, 'target'))
        # specifically test the fixer
        self.assertEqual(
            ['absolute.target.', 'relative.target.'],
            [v.target for v in _ensure_trailing_dots(record, 'target').values],
        )
