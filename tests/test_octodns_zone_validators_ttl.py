#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.ttl import ConsistentTtlAtNameZoneValidator


def _make_zone(name='unit.tests.'):
    return Zone(name, [])


def _add_record(zone, name, data, lenient=True):
    if 'ttl' not in data:
        data['ttl'] = 300
    record = Record.new(zone, name, data, lenient=lenient)
    zone.add_record(record)
    return record


class TestConsistentTtlAtNameZoneValidator(TestCase):
    def test_valid_same_ttl(self):
        zone = _make_zone()
        _add_record(zone, 'www', {'type': 'A', 'value': '1.2.3.4', 'ttl': 300})
        _add_record(zone, 'www', {'type': 'AAAA', 'value': '::1', 'ttl': 300})

        v = ConsistentTtlAtNameZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_invalid_different_ttls(self):
        zone = _make_zone()
        _add_record(zone, 'www', {'type': 'A', 'value': '1.2.3.4', 'ttl': 300})
        _add_record(zone, 'www', {'type': 'AAAA', 'value': '::1', 'ttl': 600})

        v = ConsistentTtlAtNameZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('multiple TTLs', str(reasons[0]))
        self.assertEqual(2, len(reasons[0].records))

    def test_single_record(self):
        zone = _make_zone()
        _add_record(zone, 'www', {'type': 'A', 'value': '1.2.3.4', 'ttl': 300})

        v = ConsistentTtlAtNameZoneValidator('test')
        self.assertEqual([], v.validate(zone))
