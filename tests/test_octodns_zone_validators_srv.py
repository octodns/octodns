#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.srv import SrvTargetResolvableInZoneZoneValidator


def _make_zone(name='unit.tests.'):
    return Zone(name, [])


def _add_record(zone, name, data, lenient=True):
    if 'ttl' not in data:
        data['ttl'] = 300
    return Record.new(zone, name, data, lenient=lenient)


class TestSrvTargetResolvableInZoneZoneValidator(TestCase):
    def test_srv_target_resolvable_in_zone(self):
        v = SrvTargetResolvableInZoneZoneValidator('test')
        zone = _make_zone('unit.tests.')

        # Out-of-zone target (should pass - not checked)
        srv = _add_record(
            zone,
            '_sip._tcp',
            {
                'ttl': 300,
                'type': 'SRV',
                'value': {
                    'priority': 10,
                    'weight': 60,
                    'port': 5060,
                    'target': 'sip.other.tests.',
                },
            },
        )
        zone.add_record(srv)
        self.assertEqual([], v.validate(zone))

        # In-zone target with A record (should pass)
        srv_good = _add_record(
            zone,
            '_http._tcp',
            {
                'ttl': 300,
                'type': 'SRV',
                'value': {
                    'priority': 10,
                    'weight': 50,
                    'port': 80,
                    'target': 'web.unit.tests.',
                },
            },
        )
        zone.add_record(srv_good)
        a = _add_record(
            zone, 'web', {'ttl': 300, 'type': 'A', 'values': ['1.2.3.4']}
        )
        zone.add_record(a)
        self.assertEqual([], v.validate(zone))

        # In-zone target with AAAA record (should pass)
        srv_good2 = _add_record(
            zone,
            '_https._tcp',
            {
                'ttl': 300,
                'type': 'SRV',
                'value': {
                    'priority': 10,
                    'weight': 50,
                    'port': 443,
                    'target': 'web6.unit.tests.',
                },
            },
        )
        zone.add_record(srv_good2)
        aaaa = _add_record(
            zone, 'web6', {'ttl': 300, 'type': 'AAAA', 'values': ['::1']}
        )
        zone.add_record(aaaa)
        self.assertEqual([], v.validate(zone))

        # In-zone target with missing address record (should fail)
        srv_bad = _add_record(
            zone,
            '_ldap._tcp',
            {
                'ttl': 300,
                'type': 'SRV',
                'value': {
                    'priority': 10,
                    'weight': 100,
                    'port': 389,
                    'target': 'missing.unit.tests.',
                },
            },
        )
        zone.add_record(srv_bad)
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('points to in-zone target', str(reasons[0]))
        self.assertIn('that does not exist', str(reasons[0]))
        self.assertEqual({srv_bad}, reasons[0].records)

    def test_srv_target_resolvable_multiple_targets(self):
        v = SrvTargetResolvableInZoneZoneValidator('test')
        zone = _make_zone('unit.tests.')

        # Two SRV records, both missing targets (should report both)
        srv1 = _add_record(
            zone,
            '_sip._tcp',
            {
                'ttl': 300,
                'type': 'SRV',
                'value': {
                    'priority': 10,
                    'weight': 60,
                    'port': 5060,
                    'target': 'missing1.unit.tests.',
                },
            },
        )
        zone.add_record(srv1)
        srv2 = _add_record(
            zone,
            '_xmpp._tcp',
            {
                'ttl': 300,
                'type': 'SRV',
                'value': {
                    'priority': 10,
                    'weight': 50,
                    'port': 5222,
                    'target': 'missing2.unit.tests.',
                },
            },
        )
        zone.add_record(srv2)
        reasons = v.validate(zone)
        self.assertEqual(2, len(reasons))
        records_found = {r for reason in reasons for r in reason.records}
        self.assertEqual({srv1, srv2}, records_found)
