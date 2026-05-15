#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.cname import (
    CnameCoexistenceValidator,
    CnameTargetResolvableInZoneZoneValidator,
    NoCnameLoopZoneValidator,
)


def _make_zone(name='unit.tests.'):
    return Zone(name, [])


def _add_record(zone, name, data, lenient=True):
    if 'ttl' not in data:
        data['ttl'] = 300
    return Record.new(zone, name, data, lenient=lenient)


class TestNoCnameLoopZoneValidator(TestCase):
    def test_passes(self):
        zone = _make_zone()
        cname = _add_record(
            zone, 'www', {'type': 'CNAME', 'value': 'lb.unit.tests.'}
        )
        zone.add_record(cname)
        v = NoCnameLoopZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_fails_direct(self):
        zone = _make_zone()
        cname = _add_record(
            zone, 'loop', {'type': 'CNAME', 'value': 'loop.unit.tests.'}
        )
        zone.add_record(cname)
        v = NoCnameLoopZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('Loop detected', str(reasons[0]))
        self.assertIn('loop.unit.tests. -> loop.unit.tests.', str(reasons[0]))
        self.assertIn(cname, reasons[0].records)

    def test_fails_indirect(self):
        zone = _make_zone()
        c1 = _add_record(zone, 'a', {'type': 'CNAME', 'value': 'b.unit.tests.'})
        c2 = _add_record(zone, 'b', {'type': 'CNAME', 'value': 'c.unit.tests.'})
        c3 = _add_record(zone, 'c', {'type': 'CNAME', 'value': 'a.unit.tests.'})
        zone.add_record(c1)
        zone.add_record(c2)
        zone.add_record(c3)
        v = NoCnameLoopZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        msg = str(reasons[0])
        self.assertIn('Loop detected', msg)
        self.assertIn('a.unit.tests.', msg)
        self.assertIn('b.unit.tests.', msg)
        self.assertIn('c.unit.tests.', msg)
        self.assertEqual({c1, c2, c3}, reasons[0].records)

    def test_with_alias(self):
        # apex ALIAS -> b, b CNAME -> apex
        zone = _make_zone()
        a1 = _add_record(zone, '', {'type': 'ALIAS', 'value': 'b.unit.tests.'})
        c2 = _add_record(zone, 'b', {'type': 'CNAME', 'value': 'unit.tests.'})
        zone.add_record(a1)
        zone.add_record(c2)
        v = NoCnameLoopZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        msg = str(reasons[0])
        self.assertIn('Loop detected', msg)
        self.assertIn('unit.tests.', msg)
        self.assertIn('b.unit.tests.', msg)

    def test_merging_chains(self):
        # x -> z, y -> z, z -> end (no loop; exercises overall_visited break)
        zone = _make_zone()
        c1 = _add_record(zone, 'x', {'type': 'CNAME', 'value': 'z.unit.tests.'})
        c2 = _add_record(zone, 'y', {'type': 'CNAME', 'value': 'z.unit.tests.'})
        c3 = _add_record(
            zone, 'z', {'type': 'CNAME', 'value': 'end.unit.tests.'}
        )
        zone.add_record(c1)
        zone.add_record(c2)
        zone.add_record(c3)
        v = NoCnameLoopZoneValidator('test')
        self.assertEqual([], v.validate(zone))


class TestCnameCoexistenceValidator(TestCase):
    def test_no_conflict(self):
        v = CnameCoexistenceValidator('test')
        zone = _make_zone()

        # Empty zone
        self.assertEqual([], v.validate(zone))

        # Single record, no CNAME
        a = _add_record(zone, 'www', {'type': 'A', 'value': '1.2.3.4'})
        zone.add_record(a)
        self.assertEqual([], v.validate(zone))

        # CNAME alone at a node
        cname = _add_record(
            zone, 'alias', {'type': 'CNAME', 'value': 'www.unit.tests.'}
        )
        zone.add_record(cname)
        self.assertEqual([], v.validate(zone))

    def test_cname_coexistence(self):
        v = CnameCoexistenceValidator('test')
        zone = _make_zone()

        a = _add_record(zone, 'www', {'type': 'A', 'value': '1.2.3.4'})
        cname = _add_record(
            zone, 'www', {'type': 'CNAME', 'value': 'other.unit.tests.'}
        )
        zone.add_record(a)
        zone.add_record(cname)

        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('cannot coexist', str(reasons[0]))
        node = zone._records['www']
        self.assertEqual(node, reasons[0].records)

    def test_lenient_coexistence(self):
        v = CnameCoexistenceValidator('test')
        zone = _make_zone()

        a = _add_record(
            zone,
            'www',
            {'type': 'A', 'value': '1.2.3.4', 'octodns': {'lenient': True}},
            lenient=True,
        )
        cname = _add_record(
            zone,
            'www',
            {
                'type': 'CNAME',
                'value': 'other.unit.tests.',
                'octodns': {'lenient': True},
            },
            lenient=True,
        )
        zone.add_record(a)
        zone.add_record(cname)

        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertTrue(reasons[0].lenient)


class TestCnameTargetResolvableInZoneZoneValidator(TestCase):
    def test_cname_target_resolvable_in_zone(self):
        v = CnameTargetResolvableInZoneZoneValidator('test')
        zone = _make_zone('unit.tests.')

        # Out-of-zone target (should pass - not checked)
        cname = _add_record(
            zone,
            'www',
            {'ttl': 300, 'type': 'CNAME', 'value': 'lb.other.tests.'},
        )
        zone.add_record(cname)
        self.assertEqual([], v.validate(zone))

        # In-zone target with record (should pass)
        cname_good = _add_record(
            zone,
            'app',
            {'ttl': 300, 'type': 'CNAME', 'value': 'lb.unit.tests.'},
        )
        zone.add_record(cname_good)
        a = _add_record(
            zone, 'lb', {'ttl': 300, 'type': 'A', 'values': ['1.2.3.4']}
        )
        zone.add_record(a)
        self.assertEqual([], v.validate(zone))

        # In-zone target with AAAA record (should pass)
        cname_good2 = _add_record(
            zone,
            'api',
            {'ttl': 300, 'type': 'CNAME', 'value': 'lb6.unit.tests.'},
        )
        zone.add_record(cname_good2)
        aaaa = _add_record(
            zone, 'lb6', {'ttl': 300, 'type': 'AAAA', 'values': ['::1']}
        )
        zone.add_record(aaaa)
        self.assertEqual([], v.validate(zone))

        # In-zone target with missing record (should fail)
        cname_bad = _add_record(
            zone,
            'old',
            {'ttl': 300, 'type': 'CNAME', 'value': 'missing.unit.tests.'},
        )
        zone.add_record(cname_bad)
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('points to in-zone target', str(reasons[0]))
        self.assertIn('that does not exist', str(reasons[0]))
        self.assertEqual({cname_bad}, reasons[0].records)

    def test_cname_target_resolvable_multiple_targets(self):
        v = CnameTargetResolvableInZoneZoneValidator('test')
        zone = _make_zone('unit.tests.')

        # Two CNAME records, both missing targets (should report both)
        cname1 = _add_record(
            zone,
            'old1',
            {'ttl': 300, 'type': 'CNAME', 'value': 'missing1.unit.tests.'},
        )
        zone.add_record(cname1)
        cname2 = _add_record(
            zone,
            'old2',
            {'ttl': 300, 'type': 'CNAME', 'value': 'missing2.unit.tests.'},
        )
        zone.add_record(cname2)
        reasons = v.validate(zone)
        self.assertEqual(2, len(reasons))
        records_found = {r for reason in reasons for r in reason.records}
        self.assertEqual({cname1, cname2}, records_found)

    def test_alias_target_resolvable_in_zone(self):
        v = CnameTargetResolvableInZoneZoneValidator('test')
        zone = _make_zone('unit.tests.')

        # Out-of-zone ALIAS target (should pass - not checked)
        alias = _add_record(
            zone,
            'www',
            {'ttl': 300, 'type': 'ALIAS', 'value': 'lb.other.tests.'},
        )
        zone.add_record(alias)
        self.assertEqual([], v.validate(zone))

        # In-zone target with record (should pass)
        alias_good = _add_record(
            zone,
            'app',
            {'ttl': 300, 'type': 'ALIAS', 'value': 'lb.unit.tests.'},
        )
        zone.add_record(alias_good)
        a = _add_record(
            zone, 'lb', {'ttl': 300, 'type': 'A', 'values': ['1.2.3.4']}
        )
        zone.add_record(a)
        self.assertEqual([], v.validate(zone))

        # In-zone target with missing record (should fail)
        alias_bad = _add_record(
            zone,
            'old',
            {'ttl': 300, 'type': 'ALIAS', 'value': 'missing.unit.tests.'},
        )
        zone.add_record(alias_bad)
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('ALIAS record', str(reasons[0]))
        self.assertIn('points to in-zone target', str(reasons[0]))
        self.assertIn('that does not exist', str(reasons[0]))
        self.assertEqual({alias_bad}, reasons[0].records)

    def test_mixed_cname_alias(self):
        v = CnameTargetResolvableInZoneZoneValidator('test')
        zone = _make_zone('unit.tests.')

        # Mix of CNAME and ALIAS, both missing targets
        cname_bad = _add_record(
            zone,
            'old',
            {'ttl': 300, 'type': 'CNAME', 'value': 'missing.unit.tests.'},
        )
        zone.add_record(cname_bad)
        alias_bad = _add_record(
            zone,
            'legacy',
            {'ttl': 300, 'type': 'ALIAS', 'value': 'also-missing.unit.tests.'},
        )
        zone.add_record(alias_bad)
        reasons = v.validate(zone)
        self.assertEqual(2, len(reasons))
        records_found = {r for reason in reasons for r in reason.records}
        self.assertEqual({cname_bad, alias_bad}, records_found)
