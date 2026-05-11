#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.cname import CnameCoexistenceValidator


def _make_zone(name='unit.tests.'):
    return Zone(name, [])


def _add_record(zone, name, data, lenient=False):
    if 'ttl' not in data:
        data['ttl'] = 300
    return Record.new(zone, name, data, lenient=lenient)


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
