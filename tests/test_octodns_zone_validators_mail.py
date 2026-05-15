#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.mail import (
    MailZoneValidator,
    MxTargetResolvableInZoneZoneValidator,
)


def _make_zone(name='unit.tests.'):
    return Zone(name, [])


def _add_record(zone, name, data, lenient=True):
    if 'ttl' not in data:
        data['ttl'] = 300
    return Record.new(zone, name, data, lenient=lenient)


class TestMailZoneValidator(TestCase):
    def test_mail_validator_init(self):
        v = MailZoneValidator('test')
        self.assertEqual('auto', v.mode)

        v = MailZoneValidator('test', mode='mail')
        self.assertEqual('mail', v.mode)

        v = MailZoneValidator('test', mode='no-mail')
        self.assertEqual('no-mail', v.mode)

        with self.assertRaises(ValueError):
            MailZoneValidator('test', mode='bad')

    def test_mail_mode_success(self):
        zone = _make_zone()
        # MX
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [
                    {'preference': 10, 'exchange': 'mail1.unit.tests.'},
                    {'preference': 20, 'exchange': 'mail2.unit.tests.'},
                ],
            },
        )
        zone.add_record(mx)
        # SPF (Mixed Case)
        spf = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'TXT',
                'values': ['V=SPF1 include:example.com -ALL'],
            },
        )
        zone.add_record(spf)
        # DMARC (Mixed Case, Escaped)
        dmarc = _add_record(
            zone,
            '_dmarc',
            {'ttl': 300, 'type': 'TXT', 'values': ['v=DMARC1\\; p=REJECT\\;']},
        )
        zone.add_record(dmarc)

        v = MailZoneValidator('test', mode='mail')
        self.assertEqual([], v.validate(zone))

    def test_mail_mode_failures(self):
        zone = _make_zone()
        v = MailZoneValidator('test', mode='mail')

        # Empty zone
        reasons = v.validate(zone)
        self.assertEqual(3, len(reasons))
        self.assertIn('missing MX records at the apex', str(reasons[0]))
        self.assertIn('missing an SPF TXT record', str(reasons[1]))
        self.assertIn('missing a DMARC TXT record', str(reasons[2]))

        # Multiple SPF — no longer short-circuits; other errors are also reported
        spf = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'TXT',
                'values': [
                    'v=spf1 include:a.com ~all',
                    'v=spf1 include:b.com -all',
                ],
            },
        )
        zone.add_record(spf)
        reasons = v.validate(zone)
        self.assertEqual(3, len(reasons))
        self.assertIn('has multiple SPF values', str(reasons[0]))
        self.assertIn('missing MX records at the apex', str(reasons[1]))
        self.assertIn('missing a DMARC TXT record', str(reasons[2]))

        # Clear SPF and test Multiple DMARC (Early return)
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [
                    {'preference': 10, 'exchange': 'm1.'},
                    {'preference': 20, 'exchange': 'm2.'},
                ],
            },
        )
        zone.add_record(mx)
        spf = _add_record(
            zone, '', {'ttl': 300, 'type': 'TXT', 'values': ['v=spf1 -all']}
        )
        zone.add_record(spf)
        dmarc = _add_record(
            zone,
            '_dmarc',
            {
                'ttl': 300,
                'type': 'TXT',
                'values': ['v=DMARC1\\; p=reject', 'v=DMARC1\\; p=reject'],
            },
        )
        zone.add_record(dmarc)
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('has multiple DMARC values', str(reasons[0]))

        # Single MX, Bad SPF terminator, Missing DMARC policy
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail1.unit.tests.'}],
            },
        )
        zone.add_record(mx)
        spf = _add_record(
            zone,
            '',
            {'ttl': 300, 'type': 'TXT', 'values': ['v=spf1 include:a.com']},
        )
        zone.add_record(spf)
        dmarc = _add_record(
            zone,
            '_dmarc',
            {'ttl': 300, 'type': 'TXT', 'values': ['v=DMARC1\\;']},
        )
        zone.add_record(dmarc)

        reasons = v.validate(zone)
        self.assertEqual(3, len(reasons))
        self.assertIn('should have at least 2 values', str(reasons[0]))
        self.assertIn('terminate with "~all" or "-all"', str(reasons[1]))
        self.assertIn('missing a policy', str(reasons[2]))

    def test_no_mail_mode_success(self):
        zone = _make_zone()
        # Null MX
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 0, 'exchange': '.'}],
            },
        )
        zone.add_record(mx)
        # Strict SPF (Mixed Case)
        spf = _add_record(
            zone, '', {'ttl': 300, 'type': 'TXT', 'values': ['V=SPF1 -ALL']}
        )
        zone.add_record(spf)
        # DMARC reject (Mixed Case, Escaped)
        dmarc = _add_record(
            zone,
            '_dmarc',
            {'ttl': 300, 'type': 'TXT', 'values': ['v=DMARC1\\; P=REJECT\\;']},
        )
        zone.add_record(dmarc)

        v = MailZoneValidator('test', mode='no-mail')
        # All validations pass
        self.assertEqual([], v.validate(zone))

    def test_no_mail_mode_failures(self):
        zone = _make_zone()
        v = MailZoneValidator('test', mode='no-mail')

        # Empty zone
        reasons = v.validate(zone)
        self.assertEqual(3, len(reasons))
        self.assertIn('missing a Null MX record', str(reasons[0]))
        self.assertIn('missing strict SPF TXT record', str(reasons[1]))
        self.assertIn('missing strict DMARC TXT record', str(reasons[2]))

        # Bad MX, Bad SPF, Bad DMARC
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail.'}],
            },
        )
        zone.add_record(mx)
        spf = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'TXT',
                'values': ['v=spf1 include:a.com ~all'],
            },
        )
        zone.add_record(spf)
        dmarc = _add_record(
            zone,
            '_dmarc',
            {'ttl': 300, 'type': 'TXT', 'values': ['v=DMARC1\\; p=none']},
        )
        zone.add_record(dmarc)

        reasons = v.validate(zone)
        self.assertEqual(4, len(reasons))
        self.assertIn(
            'should have at least 2 values for redundancy', str(reasons[0])
        )
        self.assertIn('should have a single Null MX record', str(reasons[1]))
        self.assertIn('should have a single strict SPF', str(reasons[2]))
        self.assertIn('should have a DMARC TXT record with', str(reasons[3]))

    def test_auto_mode(self):
        v = MailZoneValidator('test', mode='auto')

        # Auto-detects 'mail' via MX
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail.'}],
            },
        )
        zone.add_record(mx)
        reasons = v.validate(zone)
        self.assertIn('should have at least 2 values', str(reasons[0]))

        # Auto-detects 'no-mail' via Null MX
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 0, 'exchange': '.'}],
            },
        )
        zone.add_record(mx)
        reasons = v.validate(zone)
        self.assertEqual(2, len(reasons))
        self.assertIn('missing strict SPF TXT record', str(reasons[0]))
        self.assertIn('missing strict DMARC TXT record', str(reasons[1]))

        # Auto-detects 'no-mail' via strict SPF
        zone = _make_zone()
        spf = _add_record(
            zone, '', {'ttl': 300, 'type': 'TXT', 'values': ['v=spf1 -all']}
        )
        zone.add_record(spf)
        reasons = v.validate(zone)
        self.assertIn('missing a Null MX record', str(reasons[0]))

        # Auto-detects 'no-mail' via strict DMARC
        zone = _make_zone()
        dmarc = _add_record(
            zone,
            '_dmarc',
            {'ttl': 300, 'type': 'TXT', 'values': ['v=DMARC1\\; p=reject\\;']},
        )
        zone.add_record(dmarc)
        reasons = v.validate(zone)
        self.assertIn('missing a Null MX record', str(reasons[0]))

        # Non-apex MX triggers redundancy check AND sub-zone SPF validation.
        zone = _make_zone()
        mx = _add_record(
            zone,
            'sub',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail.unit.tests.'}],
            },
        )
        zone.add_record(mx)
        reasons = v.validate(zone)
        self.assertEqual(2, len(reasons))
        self.assertIn(
            'should have at least 2 values for redundancy', str(reasons[0])
        )
        self.assertIn(
            'handles mail but is missing an SPF TXT record', str(reasons[1])
        )

        # No-op with no signs
        zone = _make_zone()
        self.assertEqual([], v.validate(zone))

    def test_subzone_mail_success(self):
        # Use auto mode so apex auto-detection finds no apex signals and skips;
        # sub-domain with MX+SPF validates clean.
        zone = _make_zone()
        mx = _add_record(
            zone,
            'sub',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [
                    {'preference': 10, 'exchange': 'mail1.unit.tests.'},
                    {'preference': 20, 'exchange': 'mail2.unit.tests.'},
                ],
            },
        )
        zone.add_record(mx)
        spf = _add_record(
            zone,
            'sub',
            {
                'ttl': 300,
                'type': 'TXT',
                'values': ['V=SPF1 include:example.com -ALL'],
            },
        )
        zone.add_record(spf)
        # No _dmarc.sub record — DMARC is not required at the sub-domain level
        v = MailZoneValidator('test', mode='auto')
        self.assertEqual([], v.validate(zone))

    def test_subzone_mail_failures(self):
        # Use auto mode so apex validation does not interfere
        v = MailZoneValidator('test', mode='auto')

        # Missing SPF
        zone = _make_zone()
        zone.add_record(
            _add_record(
                zone,
                'sub',
                {
                    'ttl': 300,
                    'type': 'MX',
                    'values': [
                        {'preference': 10, 'exchange': 'mail1.unit.tests.'},
                        {'preference': 20, 'exchange': 'mail2.unit.tests.'},
                    ],
                },
            )
        )
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn(
            'handles mail but is missing an SPF TXT record', str(reasons[0])
        )

        # Bad SPF terminator
        zone.add_record(
            _add_record(
                zone,
                'sub',
                {'ttl': 300, 'type': 'TXT', 'values': ['v=spf1 include:a.com']},
            )
        )
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('terminate with "~all" or "-all"', str(reasons[0]))

        # Non-SPF TXT (TXT exists but no v=spf1 entry)
        zone = _make_zone()
        zone.add_record(
            _add_record(
                zone,
                'sub',
                {
                    'ttl': 300,
                    'type': 'MX',
                    'values': [
                        {'preference': 10, 'exchange': 'mail1.unit.tests.'},
                        {'preference': 20, 'exchange': 'mail2.unit.tests.'},
                    ],
                },
            )
        )
        zone.add_record(
            _add_record(
                zone,
                'sub',
                {'ttl': 300, 'type': 'TXT', 'values': ['some-other-txt']},
            )
        )
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn(
            'handles mail but is missing an SPF TXT record', str(reasons[0])
        )

        # Multiple SPF values
        zone = _make_zone()
        zone.add_record(
            _add_record(
                zone,
                'sub',
                {
                    'ttl': 300,
                    'type': 'MX',
                    'values': [
                        {'preference': 10, 'exchange': 'mail1.unit.tests.'},
                        {'preference': 20, 'exchange': 'mail2.unit.tests.'},
                    ],
                },
            )
        )
        zone.add_record(
            _add_record(
                zone,
                'sub',
                {
                    'ttl': 300,
                    'type': 'TXT',
                    'values': [
                        'v=spf1 include:a.com ~all',
                        'v=spf1 include:b.com -all',
                    ],
                },
            )
        )
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('has multiple SPF values', str(reasons[0]))

    def test_subzone_no_mail_success(self):
        # Use auto mode so apex auto-detection finds no apex signals and skips
        zone = _make_zone()
        zone.add_record(
            _add_record(
                zone,
                'sub',
                {
                    'ttl': 300,
                    'type': 'MX',
                    'values': [{'preference': 0, 'exchange': '.'}],
                },
            )
        )
        zone.add_record(
            _add_record(
                zone,
                'sub',
                {'ttl': 300, 'type': 'TXT', 'values': ['V=SPF1 -ALL']},
            )
        )
        v = MailZoneValidator('test', mode='auto')
        # All validations pass
        self.assertEqual([], v.validate(zone))

    def test_subzone_no_mail_failures(self):
        # Use auto mode so apex auto-detection finds no apex signals and skips
        v = MailZoneValidator('test', mode='auto')

        # Missing strict SPF
        zone = _make_zone()
        zone.add_record(
            _add_record(
                zone,
                'sub',
                {
                    'ttl': 300,
                    'type': 'MX',
                    'values': [{'preference': 0, 'exchange': '.'}],
                },
            )
        )
        reasons = v.validate(zone)
        # missing strict SPF
        self.assertEqual(1, len(reasons))
        self.assertIn('missing strict SPF TXT record', str(reasons[0]))

        # Wrong SPF value
        zone.add_record(
            _add_record(
                zone,
                'sub',
                {
                    'ttl': 300,
                    'type': 'TXT',
                    'values': ['v=spf1 include:a.com ~all'],
                },
            )
        )
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('should have a strict SPF TXT record', str(reasons[0]))

    def test_explicit_mode_propagates_to_subzones(self):
        # mode='mail': sub-zone with null MX still gets mail-mode SPF check.
        # Provide a valid apex so only sub-zone errors surface.
        def _valid_mail_apex(zone):
            zone.add_record(
                _add_record(
                    zone,
                    '',
                    {
                        'ttl': 300,
                        'type': 'MX',
                        'values': [
                            {'preference': 10, 'exchange': 'mx1.unit.tests.'},
                            {'preference': 20, 'exchange': 'mx2.unit.tests.'},
                        ],
                    },
                )
            )
            zone.add_record(
                _add_record(
                    zone,
                    '',
                    {
                        'ttl': 300,
                        'type': 'TXT',
                        'values': ['v=spf1 include:example.com -all'],
                    },
                )
            )
            zone.add_record(
                _add_record(
                    zone,
                    '_dmarc',
                    {
                        'ttl': 300,
                        'type': 'TXT',
                        'values': ['v=DMARC1\\; p=reject\\;'],
                    },
                )
            )

        def _valid_no_mail_apex(zone):
            zone.add_record(
                _add_record(
                    zone,
                    '',
                    {
                        'ttl': 300,
                        'type': 'MX',
                        'values': [{'preference': 0, 'exchange': '.'}],
                    },
                )
            )
            zone.add_record(
                _add_record(
                    zone,
                    '',
                    {'ttl': 300, 'type': 'TXT', 'values': ['v=spf1 -all']},
                )
            )
            zone.add_record(
                _add_record(
                    zone,
                    '_dmarc',
                    {
                        'ttl': 300,
                        'type': 'TXT',
                        'values': ['v=DMARC1\\; p=reject\\;'],
                    },
                )
            )

        # mode='mail': sub-zone null MX → mail mode forces SPF check (no null-MX check)
        zone = _make_zone()
        _valid_mail_apex(zone)
        zone.add_record(
            _add_record(
                zone,
                'sub',
                {
                    'ttl': 300,
                    'type': 'MX',
                    'values': [{'preference': 0, 'exchange': '.'}],
                },
            )
        )
        v = MailZoneValidator('test', mode='mail')
        reasons = v.validate(zone)
        # mail-mode SPF missing (null MX is skipped by redundancy check)
        self.assertEqual(1, len(reasons))
        self.assertIn(
            'handles mail but is missing an SPF TXT record', str(reasons[0])
        )

        # mode='no-mail': sub-zone real MX → null-MX structure check + strict SPF check
        zone = _make_zone()
        _valid_no_mail_apex(zone)
        zone.add_record(
            _add_record(
                zone,
                'sub',
                {
                    'ttl': 300,
                    'type': 'MX',
                    'values': [
                        {'preference': 10, 'exchange': 'mail1.unit.tests.'},
                        {'preference': 20, 'exchange': 'mail2.unit.tests.'},
                    ],
                },
            )
        )
        v = MailZoneValidator('test', mode='no-mail')
        reasons = v.validate(zone)
        # sub null-MX structure failure + sub missing strict SPF (apex null-MX redundancy is gone)
        self.assertEqual(2, len(reasons))
        self.assertIn('should have a single Null MX record', str(reasons[0]))
        self.assertIn('missing strict SPF TXT record', str(reasons[1]))

        # auto mode: apex no-mail + sub mail coexist cleanly when both are properly configured
        zone = _make_zone()
        _valid_no_mail_apex(zone)
        zone.add_record(
            _add_record(
                zone,
                'sub',
                {
                    'ttl': 300,
                    'type': 'MX',
                    'values': [
                        {'preference': 10, 'exchange': 'mail1.unit.tests.'},
                        {'preference': 20, 'exchange': 'mail2.unit.tests.'},
                    ],
                },
            )
        )
        zone.add_record(
            _add_record(
                zone,
                'sub',
                {
                    'ttl': 300,
                    'type': 'TXT',
                    'values': ['v=spf1 include:mail.example.com -all'],
                },
            )
        )
        v = MailZoneValidator('test', mode='auto')
        # All validations pass (apex null-MX redundancy warning is gone)
        self.assertEqual([], v.validate(zone))

    def test_null_mx_skips_redundancy_check(self):
        # Explicitly verify that Null MX records skip the redundancy check.
        # This is a regression test for the case where we want to ensure
        # that the 2-value minimum requirement is bypassed for Null MX.
        zone = _make_zone()
        # Null MX
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 0, 'exchange': '.'}],
            },
        )
        zone.add_record(mx)
        # Strict SPF
        spf = _add_record(
            zone, '', {'ttl': 300, 'type': 'TXT', 'values': ['v=spf1 -all']}
        )
        zone.add_record(spf)
        # Strict DMARC
        dmarc = _add_record(
            zone,
            '_dmarc',
            {'ttl': 300, 'type': 'TXT', 'values': ['v=DMARC1; p=reject;']},
        )
        zone.add_record(dmarc)

        v = MailZoneValidator('test', mode='no-mail')
        # All validations pass, specifically no redundancy warning for the single MX value
        self.assertEqual([], v.validate(zone))

    def test_builtin_registration(self):
        ids = [v.id for v in Zone.validators.available_validators()]
        self.assertIn('mail', ids)

    def test_builtins_in_best_practice_set(self):
        Zone.enable_zone_validators({'best-practice'})
        active_ids = [v.id for v in Zone.validators.registered()]
        self.assertIn('mail', active_ids)


class TestMxTargetResolvableInZoneZoneValidator(TestCase):
    def test_mx_target_resolvable_in_zone(self):
        v = MxTargetResolvableInZoneZoneValidator('test')
        zone = _make_zone('unit.tests.')

        # Out-of-zone target (should pass - not checked)
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail.other.tests.'}],
            },
        )
        zone.add_record(mx)
        self.assertEqual([], v.validate(zone))

        # In-zone target with A record (should pass) - use replace=True
        mx_good = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail.unit.tests.'}],
            },
        )
        zone.add_record(mx_good, replace=True)
        a = _add_record(
            zone, 'mail', {'ttl': 300, 'type': 'A', 'values': ['1.2.3.4']}
        )
        zone.add_record(a)
        self.assertEqual([], v.validate(zone))

        # In-zone target with AAAA record (should pass) - use replace=True
        mx_good2 = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 20, 'exchange': 'mail6.unit.tests.'}],
            },
        )
        zone.add_record(mx_good2, replace=True)
        aaaa = _add_record(
            zone, 'mail6', {'ttl': 300, 'type': 'AAAA', 'values': ['::1']}
        )
        zone.add_record(aaaa)
        self.assertEqual([], v.validate(zone))

        # In-zone target with missing address record (should fail) - use replace=True
        mx_bad = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [
                    {'preference': 30, 'exchange': 'missing.unit.tests.'}
                ],
            },
        )
        zone.add_record(mx_bad, replace=True)
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('points to in-zone target', str(reasons[0]))
        self.assertIn('that does not exist', str(reasons[0]))
        self.assertEqual({mx_bad}, reasons[0].records)

    def test_mx_target_resolvable_multiple_targets(self):
        v = MxTargetResolvableInZoneZoneValidator('test')
        zone = _make_zone('unit.tests.')

        # MX record with multiple values both pointing to missing in-zone targets
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [
                    {'preference': 10, 'exchange': 'missing1.unit.tests.'},
                    {'preference': 20, 'exchange': 'missing2.unit.tests.'},
                ],
            },
        )
        zone.add_record(mx)
        reasons = v.validate(zone)
        self.assertEqual(2, len(reasons))
        records_found = {r for reason in reasons for r in reason.records}
        self.assertEqual({mx}, records_found)
