#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.dname import DnameCoexistenceValidator


def _make_zone(name='unit.tests.'):
    return Zone(name, [])


def _add_record(zone, name, data, lenient=True):
    if 'ttl' not in data:
        data['ttl'] = 300
    return Record.new(zone, name, data, lenient=lenient)


class TestDnameCoexistenceValidator(TestCase):
    def test_passes_empty_or_no_dname(self):
        v = DnameCoexistenceValidator('test')
        zone = _make_zone()

        # Empty zone
        self.assertEqual([], v.validate(zone))

        # Single A record
        a = _add_record(zone, 'www', {'type': 'A', 'value': '1.2.3.4'})
        zone.add_record(a)
        self.assertEqual([], v.validate(zone))

    def test_passes_dname_alone_or_with_other_allowed(self):
        v = DnameCoexistenceValidator('test')
        zone = _make_zone()

        # DNAME at non-apex with A record (allowed coexistence)
        dname = _add_record(
            zone, 'sub', {'type': 'DNAME', 'value': 'target.other.'}
        )
        a = _add_record(zone, 'sub', {'type': 'A', 'value': '1.2.3.4'})
        zone.add_record(dname)
        zone.add_record(a)

        self.assertEqual([], v.validate(zone))

    def test_fails_dname_cname_coexistence(self):
        v = DnameCoexistenceValidator('test')
        zone = _make_zone()

        dname = _add_record(
            zone, 'sub', {'type': 'DNAME', 'value': 'target.other.'}
        )
        cname = _add_record(
            zone, 'sub', {'type': 'CNAME', 'value': 'target.another.'}
        )
        zone.add_record(dname)
        zone.add_record(cname)

        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('cannot coexist with CNAME', str(reasons[0]))
        self.assertEqual({dname, cname}, reasons[0].records)

    def test_dname_ns_coexistence(self):
        v = DnameCoexistenceValidator('test')

        # DNAME + NS at apex is allowed
        zone_apex = _make_zone()
        dname_apex = _add_record(
            zone_apex, '', {'type': 'DNAME', 'value': 'target.other.'}
        )
        ns_apex = _add_record(
            zone_apex,
            '',
            {'type': 'NS', 'values': ['ns1.other.', 'ns2.other.']},
        )
        zone_apex.add_record(dname_apex)
        zone_apex.add_record(ns_apex)
        self.assertEqual([], v.validate(zone_apex))

        # DNAME + NS at non-apex is NOT allowed
        zone_sub = _make_zone()
        dname_sub = _add_record(
            zone_sub, 'sub', {'type': 'DNAME', 'value': 'target.other.'}
        )
        ns_sub = _add_record(
            zone_sub,
            'sub',
            {'type': 'NS', 'values': ['ns1.other.', 'ns2.other.']},
        )
        zone_sub.add_record(dname_sub)
        zone_sub.add_record(ns_sub)

        reasons = v.validate(zone_sub)
        self.assertEqual(1, len(reasons))
        self.assertIn(
            'cannot coexist with NS at a non-apex node', str(reasons[0])
        )
        self.assertEqual({dname_sub, ns_sub}, reasons[0].records)

    def test_fails_occlusion(self):
        v = DnameCoexistenceValidator('test')
        zone = _make_zone()

        dname = _add_record(
            zone, 'sub', {'type': 'DNAME', 'value': 'target.other.'}
        )
        # Record at subordinate name 'child.sub' (occluded)
        a_child = _add_record(
            zone, 'child.sub', {'type': 'A', 'value': '1.2.3.4'}
        )
        # Record at unrelated name 'childsub' (not occluded)
        a_unrelated = _add_record(
            zone, 'childsub', {'type': 'A', 'value': '5.6.7.8'}
        )
        # Record at same owner name 'sub' (not occluded)
        a_same = _add_record(zone, 'sub', {'type': 'A', 'value': '9.10.11.12'})

        zone.add_record(dname)
        zone.add_record(a_child)
        zone.add_record(a_unrelated)
        zone.add_record(a_same)

        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('is occluded by DNAME', str(reasons[0]))
        self.assertEqual({a_child}, reasons[0].records)

    def test_fails_occlusion_at_apex(self):
        v = DnameCoexistenceValidator('test')
        zone = _make_zone()

        # DNAME at apex occludes everything else in the zone
        dname = _add_record(
            zone, '', {'type': 'DNAME', 'value': 'target.other.'}
        )
        a_child = _add_record(zone, 'www', {'type': 'A', 'value': '1.2.3.4'})
        zone.add_record(dname)
        zone.add_record(a_child)

        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('is occluded by DNAME', str(reasons[0]))
        self.assertEqual({a_child}, reasons[0].records)

    def test_multiple_dnames(self):
        v = DnameCoexistenceValidator('test')
        zone = _make_zone()

        d1 = _add_record(
            zone, 'sub1', {'type': 'DNAME', 'value': 'target1.other.'}
        )
        d2 = _add_record(
            zone, 'sub2', {'type': 'DNAME', 'value': 'target2.other.'}
        )

        a1 = _add_record(zone, 'child.sub1', {'type': 'A', 'value': '1.2.3.4'})
        a2 = _add_record(zone, 'child.sub2', {'type': 'A', 'value': '5.6.7.8'})

        zone.add_record(d1)
        zone.add_record(d2)
        zone.add_record(a1)
        zone.add_record(a2)

        reasons = v.validate(zone)
        self.assertEqual(2, len(reasons))
        occluded_records = {r for reason in reasons for r in reason.records}
        self.assertEqual({a1, a2}, occluded_records)
