#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.cname_loops import NoCnameLoopZoneValidator


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
