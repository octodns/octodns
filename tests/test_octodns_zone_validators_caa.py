#
#
#

from unittest import TestCase

from helpers import zone_validators_snapshot

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.caa import ApexCaaPresenceZoneValidator


def _make_zone(name='unit.tests.'):
    return Zone(name, [])


def _add_record(zone, name, data, lenient=True):
    if 'ttl' not in data:
        data['ttl'] = 300
    return Record.new(zone, name, data, lenient=lenient)


class TestApexCaaPresenceZoneValidator(TestCase):
    def test_apex_caa_presence_passes(self):
        zone = _make_zone()
        caa = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'CAA',
                'value': {
                    'flags': 0,
                    'tag': 'issue',
                    'value': 'ca.example.net',
                },
            },
        )
        zone.add_record(caa)
        v = ApexCaaPresenceZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_apex_caa_presence_passes_multiple(self):
        zone = _make_zone()
        caa1 = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'CAA',
                'value': {
                    'flags': 0,
                    'tag': 'issue',
                    'value': 'ca.example.net',
                },
            },
        )
        caa2 = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'CAA',
                'value': {
                    'flags': 0,
                    'tag': 'issuewild',
                    'value': 'ca2.example.net',
                },
            },
        )
        # Multiple records at same name requires replace=True for the second
        zone.add_record(caa1)
        zone.add_record(caa2, replace=True)
        v = ApexCaaPresenceZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_apex_caa_presence_fails(self):
        zone = _make_zone()
        v = ApexCaaPresenceZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('has no CAA records at the apex', reasons[0].reason)

    def test_apex_caa_presence_fails_no_records_at_all(self):
        zone = _make_zone()
        # Add some other records but no CAA
        a = _add_record(zone, '', {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'})
        zone.add_record(a)
        v = ApexCaaPresenceZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('has no CAA records at the apex', reasons[0].reason)

    def test_builtin_registration(self):
        ids = [v.id for v in Zone.validators.available_validators()]
        self.assertIn('apex-caa-presence', ids)

    def test_builtins_in_best_practice_set(self):
        with zone_validators_snapshot():
            Zone.enable_zone_validators({'best-practice'})
            active_ids = [v.id for v in Zone.validators.registered()]
            self.assertIn('apex-caa-presence', active_ids)
