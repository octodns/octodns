#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.ns import (
    GlueForInZoneNsZoneValidator,
    MultiValueNsZoneValidator,
    NsTargetNotCnameZoneValidator,
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


class TestMultiValueNsZoneValidator(TestCase):
    def test_multi_value_ns(self):
        v = MultiValueNsZoneValidator('test')
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
        # Add a non-NS record to cover the branch in validate
        a = _add_record(
            zone, 'www', {'ttl': 300, 'type': 'A', 'values': ['1.2.3.4']}
        )
        zone.add_record(a)
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

        # 1 NS value for sub-delegation
        ns_sub = _add_record(
            zone, 'sub', {'ttl': 300, 'type': 'NS', 'values': ['ns3.com.']}
        )
        zone.add_record(ns_sub)
        reasons = sorted(
            v.validate(zone), key=lambda r: list(r.records)[0].fqdn
        )
        self.assertEqual(2, len(reasons))
        self.assertIn('sub.unit.tests.', str(reasons[0]))
        self.assertIn('unit.tests.', str(reasons[1]))
        self.assertEqual({ns_sub}, reasons[0].records)


class TestNsTargetNotCnameZoneValidator(TestCase):
    def test_empty_zone(self):
        v = NsTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        self.assertEqual([], v.validate(zone))

    def test_out_of_zone_target(self):
        v = NsTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        ns = _add_record(
            zone, '', {'type': 'NS', 'values': ['ns1.other.tests.']}
        )
        zone.add_record(ns)
        self.assertEqual([], v.validate(zone))

    def test_in_zone_target_no_cname(self):
        v = NsTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        ns = _add_record(
            zone, 'sub', {'type': 'NS', 'values': ['ns1.unit.tests.']}
        )
        zone.add_record(ns)
        a = _add_record(zone, 'ns1', {'type': 'A', 'values': ['1.2.3.4']})
        zone.add_record(a)
        self.assertEqual([], v.validate(zone))

    def test_in_zone_target_is_cname(self):
        v = NsTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        ns = _add_record(
            zone, 'sub', {'type': 'NS', 'values': ['ns1.unit.tests.']}
        )
        zone.add_record(ns)
        cname = _add_record(
            zone, 'ns1', {'type': 'CNAME', 'value': 'real.unit.tests.'}
        )
        zone.add_record(cname)
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('NS record "sub.unit.tests."', str(reasons[0]))
        self.assertIn('ns1.unit.tests.', str(reasons[0]))
        self.assertIn('is a CNAME', str(reasons[0]))
        self.assertEqual({ns}, reasons[0].records)

    def test_multiple_targets_mixed(self):
        v = NsTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        ns = _add_record(
            zone,
            'sub',
            {'type': 'NS', 'values': ['ns1.unit.tests.', 'ns2.unit.tests.']},
        )
        zone.add_record(ns)
        cname = _add_record(
            zone, 'ns1', {'type': 'CNAME', 'value': 'real.unit.tests.'}
        )
        zone.add_record(cname)
        a = _add_record(zone, 'ns2', {'type': 'A', 'values': ['1.2.3.4']})
        zone.add_record(a)
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('ns1.unit.tests.', str(reasons[0]))

    def test_builtin_registration(self):
        ids = [v.id for v in Zone.validators.available_validators()]
        self.assertIn('ns-target-not-cname', ids)

    def test_builtins_in_strict_set(self):
        Zone.enable_zone_validators({'strict'})
        active_ids = [v.id for v in Zone.validators.registered()]
        self.assertIn('ns-target-not-cname', active_ids)
