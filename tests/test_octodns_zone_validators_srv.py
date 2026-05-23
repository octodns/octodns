#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.srv import (
    SrvTargetNotCnameZoneValidator,
    SrvTargetResolvableInZoneZoneValidator,
)


def _make_zone(name='unit.tests.'):
    return Zone(name, [])


def _add_record(zone, name, data, lenient=True):
    if 'ttl' not in data:
        data['ttl'] = 300
    return Record.new(zone, name, data, lenient=lenient)


class TestSrvTargetNotCnameZoneValidator(TestCase):
    def test_empty_zone(self):
        v = SrvTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        self.assertEqual([], v.validate(zone))

    def test_out_of_zone_target(self):
        v = SrvTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        srv = _add_record(
            zone,
            '_http._tcp',
            {
                'type': 'SRV',
                'values': [
                    {
                        'priority': 10,
                        'weight': 5,
                        'port': 80,
                        'target': 'svc.other.tests.',
                    }
                ],
            },
        )
        zone.add_record(srv)
        self.assertEqual([], v.validate(zone))

    def test_in_zone_target_no_cname(self):
        v = SrvTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        srv = _add_record(
            zone,
            '_http._tcp',
            {
                'type': 'SRV',
                'values': [
                    {
                        'priority': 10,
                        'weight': 5,
                        'port': 80,
                        'target': 'svc.unit.tests.',
                    }
                ],
            },
        )
        zone.add_record(srv)
        a = _add_record(zone, 'svc', {'type': 'A', 'values': ['1.2.3.4']})
        zone.add_record(a)
        self.assertEqual([], v.validate(zone))

    def test_in_zone_target_is_cname(self):
        v = SrvTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        srv = _add_record(
            zone,
            '_http._tcp',
            {
                'type': 'SRV',
                'values': [
                    {
                        'priority': 10,
                        'weight': 5,
                        'port': 80,
                        'target': 'svc.unit.tests.',
                    }
                ],
            },
        )
        zone.add_record(srv)
        cname = _add_record(
            zone, 'svc', {'type': 'CNAME', 'value': 'real.unit.tests.'}
        )
        zone.add_record(cname)
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('SRV record "_http._tcp.unit.tests."', str(reasons[0]))
        self.assertIn('svc.unit.tests.', str(reasons[0]))
        self.assertIn('is a CNAME', str(reasons[0]))
        self.assertEqual({srv}, reasons[0].records)

    def test_dot_target_skipped(self):
        v = SrvTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        srv = _add_record(
            zone,
            '_http._tcp',
            {
                'type': 'SRV',
                'values': [
                    {'priority': 0, 'weight': 0, 'port': 0, 'target': '.'}
                ],
            },
        )
        zone.add_record(srv)
        self.assertEqual([], v.validate(zone))

    def test_multiple_targets_mixed(self):
        v = SrvTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        srv = _add_record(
            zone,
            '_http._tcp',
            {
                'type': 'SRV',
                'values': [
                    {
                        'priority': 10,
                        'weight': 5,
                        'port': 80,
                        'target': 'svc1.unit.tests.',
                    },
                    {
                        'priority': 20,
                        'weight': 5,
                        'port': 80,
                        'target': 'svc2.unit.tests.',
                    },
                ],
            },
        )
        zone.add_record(srv)
        cname = _add_record(
            zone, 'svc1', {'type': 'CNAME', 'value': 'real.unit.tests.'}
        )
        zone.add_record(cname)
        a = _add_record(zone, 'svc2', {'type': 'A', 'values': ['1.2.3.4']})
        zone.add_record(a)
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('svc1.unit.tests.', str(reasons[0]))

    def test_builtin_registration(self):
        ids = [v.id for v in Zone.validators.available_validators()]
        self.assertIn('srv-target-not-cname', ids)

    def test_builtins_in_strict_set(self):
        Zone.enable_zone_validators({'strict'})
        active_ids = [v.id for v in Zone.validators.registered()]
        self.assertIn('srv-target-not-cname', active_ids)


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
