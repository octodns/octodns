#
#
#

from unittest import TestCase

from helpers import zone_validators_snapshot

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.caa import CaaZoneValidator


def _make_zone(name='unit.tests.'):
    return Zone(name, [])


def _add_record(zone, name, data, lenient=True):
    if 'ttl' not in data:
        data['ttl'] = 300
    return Record.new(zone, name, data, lenient=lenient)


class TestCaaZoneValidator(TestCase):
    """Tests for the comprehensive CAA best-practice validator."""

    def test_presence_required_no_caa_at_all_fails(self):
        zone = _make_zone()
        v = CaaZoneValidator('test', presence='required')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('has no CAA records at the apex', reasons[0].reason)

    def test_presence_optional_no_caa_passes(self):
        zone = _make_zone()
        v = CaaZoneValidator('test', presence='optional')
        self.assertEqual([], v.validate(zone))

    def test_presence_required_no_caa_with_other_records_fails(self):
        zone = _make_zone()
        a = _add_record(zone, '', {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'})
        zone.add_record(a)
        v = CaaZoneValidator('test', presence='required')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('has no CAA records at the apex', reasons[0].reason)

    def test_only_iodef_fails_no_issue_policy(self):
        """Only iodef without issue/issuewild triggers check 1."""
        zone = _make_zone()
        caa = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'CAA',
                'value': {
                    'flags': 0,
                    'tag': 'iodef',
                    'value': 'http://iodef.example.com/',
                },
            },
        )
        zone.add_record(caa)
        v = CaaZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn(
            'has no ``issue`` or ``issuewild`` tag', reasons[0].reason
        )

    def test_issue_and_issuewild_passes_no_iodef(self):
        """Both issue and issuewild present, but missing iodef."""
        zone = _make_zone()
        caa = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'CAA',
                'values': [
                    {'flags': 0, 'tag': 'issue', 'value': 'ca.example.net'},
                    {
                        'flags': 0,
                        'tag': 'issuewild',
                        'value': 'ca2.example.net',
                    },
                ],
            },
        )
        zone.add_record(caa)
        v = CaaZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual([], reasons)

    def test_full_compliance_all_pass(self):
        """issue + issuewild + iodef present — fully compliant."""
        zone = _make_zone()
        caa = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'CAA',
                'values': [
                    {'flags': 0, 'tag': 'issue', 'value': 'ca.example.net'},
                    {
                        'flags': 0,
                        'tag': 'issuewild',
                        'value': 'ca2.example.net',
                    },
                    {
                        'flags': 0,
                        'tag': 'iodef',
                        'value': 'http://iodef.example.com/',
                    },
                ],
            },
        )
        zone.add_record(caa)
        v = CaaZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_only_issue_recommends_issuewild(self):
        """Only issue triggers missing-issuewild."""
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
        v = CaaZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('has ``issue`` but no ``issuewild``', reasons[0].reason)

    def test_subdomain_caa_validation(self):
        """Validates that CAA records on subdomains are also checked."""
        zone = _make_zone()
        # Apex is fine (optional mode)
        # Subdomain has only issue
        caa = _add_record(
            zone,
            'sub',
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
        v = CaaZoneValidator('test')
        reasons = v.validate(zone)
        # Should have warnings for missing issuewild at sub.unit.tests.
        self.assertEqual(1, len(reasons))
        self.assertIn(
            'CAA record "sub.unit.tests." has ``issue`` but no ``issuewild``',
            reasons[0].reason,
        )

    def test_invalid_presence_mode_raises(self):
        with self.assertRaises(ValueError):
            CaaZoneValidator('test', presence='invalid')

    # --- ValidationReason attaches records ---

    def test_validation_reason_attaches_records(self):
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
        v = CaaZoneValidator('test')
        reasons = v.validate(zone)
        self.assertTrue(len(reasons) >= 1)
        for reason in reasons:
            self.assertIn(caa, reason.records)

    # --- Registration ---

    def test_builtin_registration(self):
        ids = [v.id for v in Zone.validators.available_validators()]
        self.assertIn('caa-best-practices', ids)

    def test_builtins_in_best_practice_set(self):
        with zone_validators_snapshot():
            Zone.enable_zone_validators({'best-practice'})
            active_ids = [v.id for v in Zone.validators.registered()]
            self.assertIn('caa-best-practices', active_ids)
