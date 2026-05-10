#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.ns import (
    GlueForInZoneNsZoneValidator,
    MultiValueApexNsZoneValidator,
)


def _make_zone(name='unit.tests.'):
    return Zone(name, [])


def _add_record(zone, name, data, lenient=True):
    if 'ttl' not in data:
        data['ttl'] = 300
    return Record.new(zone, name, data, lenient=lenient)


class TestGlueForInZoneNsZoneValidator(TestCase):
    def test_glue_for_in_zone_ns(self):
        v = GlueForInZoneNsZoneValidator('test')
        zone = _make_zone('unit.tests.')

        # Out-of-zone target
        ns = _add_record(
            zone, '', {'ttl': 300, 'type': 'NS', 'values': ['ns1.other.tests.']}
        )
        zone.add_record(ns)
        self.assertEqual([], v.validate(zone))

        # In-zone target with A record
        ns = _add_record(
            zone,
            'sub',
            {'ttl': 300, 'type': 'NS', 'values': ['ns1.unit.tests.']},
        )
        zone.add_record(ns)
        a = _add_record(
            zone, 'ns1', {'ttl': 300, 'type': 'A', 'values': ['1.2.3.4']}
        )
        zone.add_record(a)
        self.assertEqual([], v.validate(zone))

        # In-zone target with AAAA record
        ns = _add_record(
            zone,
            'sub2',
            {'ttl': 300, 'type': 'NS', 'values': ['ns2.unit.tests.']},
        )
        zone.add_record(ns)
        aaaa = _add_record(
            zone, 'ns2', {'ttl': 300, 'type': 'AAAA', 'values': ['::1']}
        )
        zone.add_record(aaaa)
        self.assertEqual([], v.validate(zone))

        # In-zone target with missing A/AAAA
        ns_bad = _add_record(
            zone,
            'bad',
            {'ttl': 300, 'type': 'NS', 'values': ['ns3.unit.tests.']},
        )
        zone.add_record(ns_bad)
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('without glue records', str(reasons[0]))
        self.assertEqual({ns_bad}, reasons[0].records)


class TestMultiValueApexNsZoneValidator(TestCase):
    def test_multi_value_apex_ns(self):
        v = MultiValueApexNsZoneValidator('test')
        zone = _make_zone('unit.tests.')

        # No NS at apex (not this validator's job to care if it's missing entirely)
        self.assertEqual([], v.validate(zone))

        # 2 NS values at apex
        ns = _add_record(
            zone,
            '',
            {'ttl': 300, 'type': 'NS', 'values': ['ns1.com.', 'ns2.com.']},
        )
        zone.add_record(ns)
        self.assertEqual([], v.validate(zone))

        # 1 NS value at apex
        ns2 = _add_record(
            zone, '', {'ttl': 300, 'type': 'NS', 'values': ['ns1.com.']}
        )
        zone.add_record(ns2, replace=True)
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('at least 2 are recommended', str(reasons[0]))
        self.assertEqual({ns2}, reasons[0].records)
