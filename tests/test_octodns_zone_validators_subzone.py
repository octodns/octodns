#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.subzone import SubzoneRecordValidator


def _make_zone(name='unit.tests.', sub_zones=None):
    return Zone(name, sub_zones or [])


def _add_record(zone, name, data, lenient=False):
    if 'ttl' not in data:
        data['ttl'] = 300
    return Record.new(zone, name, data, lenient=lenient)


class TestSubzoneRecordValidator(TestCase):
    def test_no_subzones(self):
        v = SubzoneRecordValidator('test')
        zone = _make_zone()

        a = _add_record(zone, 'www', {'type': 'A', 'value': '1.2.3.4'})
        zone.add_record(a)
        self.assertEqual([], v.validate(zone))

    def test_ns_at_subzone_boundary_ok(self):
        v = SubzoneRecordValidator('test')
        zone = _make_zone(sub_zones=['sub'])

        ns = _add_record(
            zone,
            'sub',
            {'type': 'NS', 'values': ['ns1.example.com.', 'ns2.example.com.']},
        )
        zone.add_record(ns)
        self.assertEqual([], v.validate(zone))

    def test_ds_at_subzone_boundary_ok(self):
        v = SubzoneRecordValidator('test')
        zone = _make_zone(sub_zones=['sub'])

        ds = _add_record(
            zone,
            'sub',
            {
                'type': 'DS',
                'values': [
                    {
                        'key_tag': 1,
                        'algorithm': 1,
                        'digest_type': 1,
                        'digest': 'ab',
                    }
                ],
            },
        )
        zone.add_record(ds)
        self.assertEqual([], v.validate(zone))

    def test_non_ns_at_subzone_boundary(self):
        v = SubzoneRecordValidator('test')
        zone = _make_zone(sub_zones=['sub'])

        a = _add_record(zone, 'sub', {'type': 'A', 'value': '1.2.3.4'})
        zone.add_record(a)

        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('not of type NS or DS', str(reasons[0]))
        self.assertEqual({a}, reasons[0].records)

    def test_record_under_subzone(self):
        v = SubzoneRecordValidator('test')
        zone = _make_zone(sub_zones=['sub'])

        a = _add_record(zone, 'foo.sub', {'type': 'A', 'value': '1.2.3.4'})
        zone.add_record(a)

        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('under a managed subzone', str(reasons[0]))
        self.assertEqual({a}, reasons[0].records)

    def test_non_subzone_record_ok(self):
        v = SubzoneRecordValidator('test')
        zone = _make_zone(sub_zones=['sub'])

        # Record that happens to end with subzone name but has no dot separator
        a = _add_record(zone, 'notsub', {'type': 'A', 'value': '1.2.3.4'})
        zone.add_record(a)
        self.assertEqual([], v.validate(zone))
