#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.mail import (
    MailZoneValidator,
    MxTargetNotCnameZoneValidator,
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
        self.assertEqual(2, v.min_mx)
        # default regexes are compiled and stored
        self.assertEqual(
            len(MailZoneValidator.DEFAULT_SINGLE_MX_REGEXES),
            len(v._single_mx_res),
        )

        v = MailZoneValidator('test', mode='mail')
        self.assertEqual('mail', v.mode)

        v = MailZoneValidator('test', mode='no-mail')
        self.assertEqual('no-mail', v.mode)

        v = MailZoneValidator('test', min_mx=1)
        self.assertEqual(1, v.min_mx)

        # user regexes are appended to the defaults
        v = MailZoneValidator('test', single_mx_regexes=[r'\.example\.com\.$'])
        self.assertEqual(
            len(MailZoneValidator.DEFAULT_SINGLE_MX_REGEXES) + 1,
            len(v._single_mx_res),
        )

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

        # Auto-detects 'no-mail' via strict SPF (no apex MX)
        zone = _make_zone()
        spf = _add_record(
            zone, '', {'ttl': 300, 'type': 'TXT', 'values': ['v=spf1 -all']}
        )
        zone.add_record(spf)
        reasons = v.validate(zone)
        self.assertIn('missing a Null MX record', str(reasons[0]))

        # Auto-detects 'mail' via non-strict SPF fallback (no apex MX, but SPF
        # is sender-permitting so the zone must handle outbound mail)
        zone = _make_zone()
        spf = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'TXT',
                'values': ['v=spf1 include:_spf.example.com -all'],
            },
        )
        zone.add_record(spf)
        reasons = v.validate(zone)
        # mail mode: missing MX and missing DMARC
        self.assertIn('missing MX records at the apex', str(reasons[0]))
        self.assertIn('missing a DMARC TXT record', str(reasons[1]))

        # Lone DMARC (any policy) is a no-op in auto mode — DMARC p= cannot
        # distinguish mail from no-mail zones (issue #1422), so a lone DMARC
        # record does not trigger mode enforcement.
        zone = _make_zone()
        dmarc = _add_record(
            zone,
            '_dmarc',
            {'ttl': 300, 'type': 'TXT', 'values': ['v=DMARC1\\; p=reject\\;']},
        )
        zone.add_record(dmarc)
        self.assertEqual([], v.validate(zone))

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

    def test_dmarc_brittle_fixes(self):
        # 1. A lone DMARC record (in various valid formats) is a no-op in auto
        # mode — DMARC policy cannot distinguish mail from no-mail zones
        # (issue #1422), so only MX or SPF at the apex trigger mode detection.
        formats = [
            'v=DMARC1\\;p=reject\\;rua=mailto:dmarc@unit.tests',
            'v=DMARC1\\; p=reject\\; rua=mailto:dmarc@unit.tests',
            'v=DMARC1\\; p = reject\\;',
            'v=DMARC1\\;p = reject',
        ]
        v_auto = MailZoneValidator('test', mode='auto')
        for fmt in formats:
            zone = _make_zone()
            dmarc = _add_record(
                zone, '_dmarc', {'ttl': 300, 'type': 'TXT', 'values': [fmt]}
            )
            zone.add_record(dmarc)
            reasons = v_auto.validate(zone)
            # Lone DMARC is a no-op
            self.assertEqual([], reasons)

        # 2. Validation of policy presence in mail mode with different spaces / tags
        v_mail = MailZoneValidator('test', mode='mail')
        for fmt in formats:
            zone = _make_zone()
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
            spf = _add_record(
                zone, '', {'ttl': 300, 'type': 'TXT', 'values': ['v=spf1 -all']}
            )
            zone.add_record(spf)
            dmarc = _add_record(
                zone, '_dmarc', {'ttl': 300, 'type': 'TXT', 'values': [fmt]}
            )
            zone.add_record(dmarc)
            reasons = v_mail.validate(zone)
            # Should pass successfully without saying policy is missing
            self.assertEqual([], reasons)

        # 3. Validation in no-mail mode with different spaces / tags
        v_nomail = MailZoneValidator('test', mode='no-mail')
        for fmt in formats:
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
            spf = _add_record(
                zone, '', {'ttl': 300, 'type': 'TXT', 'values': ['v=spf1 -all']}
            )
            zone.add_record(spf)
            dmarc = _add_record(
                zone, '_dmarc', {'ttl': 300, 'type': 'TXT', 'values': [fmt]}
            )
            zone.add_record(dmarc)
            reasons = v_nomail.validate(zone)
            # Should pass successfully
            self.assertEqual([], reasons)

        # 4. Helper method direct tests for 100% branch/statement coverage
        self.assertEqual({}, v_auto._parse_dmarc_tags(None))
        self.assertEqual({}, v_auto._parse_dmarc_tags(''))
        self.assertEqual(
            {'v': 'dmarc1', 'p': 'reject', 'extra_tag_without_equals': ''},
            v_auto._parse_dmarc_tags(
                'v=dmarc1; p=reject; extra_tag_without_equals'
            ),
        )

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
        # Use auto mode so apex auto-detection finds no apex signals and skips
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

    def test_auto_mode_mx_wins_over_spf(self):
        # MX is the primary detection signal; a real MX + strict SPF 'v=spf1
        # -all' (receive-only domain) must be treated as 'mail', not 'no-mail',
        # because the MX record shows it receives mail.
        v = MailZoneValidator('test', mode='auto')
        zone = _make_zone()
        zone.add_record(
            _add_record(
                zone,
                '',
                {
                    'type': 'MX',
                    'values': [
                        {'preference': 10, 'exchange': 'mx1.unit.tests.'},
                        {'preference': 20, 'exchange': 'mx2.unit.tests.'},
                    ],
                },
            )
        )
        # Strict no-send SPF alongside real MX (receive-only domain)
        zone.add_record(
            _add_record(zone, '', {'type': 'TXT', 'values': ['v=spf1 -all']})
        )
        zone.add_record(
            _add_record(
                zone,
                '_dmarc',
                {'type': 'TXT', 'values': ['v=DMARC1\\; p=reject\\;']},
            )
        )
        # Auto should pick 'mail' (MX wins) and validate cleanly
        self.assertEqual([], v.validate(zone))

    def test_dmarc_policy_variants_with_mail(self):
        # Regression guard: p=quarantine and p=none with a real mail-handling
        # zone should also validate cleanly — only the detection bug changed.
        v = MailZoneValidator('test', mode='auto')
        for policy in ('quarantine', 'none'):
            zone = _make_zone()
            zone.add_record(
                _add_record(
                    zone,
                    '',
                    {
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
                        'type': 'TXT',
                        'values': ['v=spf1 include:_spf.example.com -all'],
                    },
                )
            )
            zone.add_record(
                _add_record(
                    zone,
                    '_dmarc',
                    {'type': 'TXT', 'values': [f'v=DMARC1\\; p={policy}\\;']},
                )
            )
            self.assertEqual(
                [], v.validate(zone), f'p={policy} should validate cleanly'
            )

    def test_dmarc_reject_with_mail_handling(self):
        # issue #1422: a real mail-handling zone (real MX + sender-permitting
        # SPF) that publishes a DMARC p=reject policy must be detected as
        # 'mail', not 'no-mail'. p=reject is a receiver-side alignment policy
        # — it is the recommended best practice for domains that DO send mail
        # and must not be treated as a no-mail signal.
        v = MailZoneValidator('test', mode='auto')
        zone = _make_zone()
        zone.add_record(
            _add_record(
                zone,
                '',
                {
                    'type': 'MX',
                    'values': [
                        {'preference': 10, 'exchange': 'aspmx.l.google.com.'},
                        {
                            'preference': 20,
                            'exchange': 'alt1.aspmx.l.google.com.',
                        },
                    ],
                },
            )
        )
        zone.add_record(
            _add_record(
                zone,
                '',
                {
                    'type': 'TXT',
                    'values': ['v=spf1 include:_spf.google.com -all'],
                },
            )
        )
        zone.add_record(
            _add_record(
                zone,
                '_dmarc',
                {
                    'type': 'TXT',
                    'values': [
                        'v=DMARC1\\; p=reject\\; rua=mailto:dmarc@unit.tests'
                    ],
                },
            )
        )
        self.assertEqual([], v.validate(zone))

    def _make_valid_mail_zone(self, mx_values):
        '''Helper: build a zone that passes all mail checks except potentially
        redundancy, using the given mx_values list.'''
        zone = _make_zone()
        zone.add_record(
            _add_record(zone, '', {'type': 'MX', 'values': mx_values})
        )
        zone.add_record(
            _add_record(
                zone,
                '',
                {'type': 'TXT', 'values': ['v=spf1 include:example.com -all']},
            )
        )
        zone.add_record(
            _add_record(
                zone,
                '_dmarc',
                {'type': 'TXT', 'values': ['v=DMARC1\\; p=reject\\;']},
            )
        )
        return zone

    def test_single_mx_provider_sendgrid_exempt(self):
        # A single-value apex MX pointing at SendGrid should not trigger the
        # redundancy check.
        zone = self._make_valid_mail_zone(
            [{'preference': 10, 'exchange': 'mx.sendgrid.net.'}]
        )
        v = MailZoneValidator('test', mode='mail')
        self.assertEqual([], v.validate(zone))

    def test_single_mx_provider_aws_ses_exempt(self):
        # Amazon SES uses region-specific inbound-smtp hostnames; all should be
        # exempt.
        for region_host in (
            'inbound-smtp.us-east-1.amazonaws.com.',
            'inbound-smtp.us-west-2.amazonaws.com.',
            'inbound-smtp.eu-west-1.amazonaws.com.',
        ):
            zone = self._make_valid_mail_zone(
                [{'preference': 10, 'exchange': region_host}]
            )
            v = MailZoneValidator('test', mode='mail')
            self.assertEqual(
                [], v.validate(zone), f'{region_host} should be exempt'
            )

        # A single amazonaws.com host that is NOT an SES inbound endpoint
        # must still be flagged.
        zone = self._make_valid_mail_zone(
            [{'preference': 10, 'exchange': 'smtp.us-east-1.amazonaws.com.'}]
        )
        v = MailZoneValidator('test', mode='mail')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('should have at least 2 values', str(reasons[0]))

    def test_single_mx_provider_matches_without_trailing_dot(self):
        # A known single-MX provider's exchange must still be recognized as
        # exempt from the redundancy check even without a trailing dot (e.g.
        # when the `mx-value-best-practice` trailing-dot validator has been
        # disabled for the zone, or the data simply omits it).
        zone = self._make_valid_mail_zone(
            [{'preference': 10, 'exchange': 'mx.sendgrid.net'}]
        )
        v = MailZoneValidator('test', mode='mail')
        self.assertEqual([], v.validate(zone))

    def test_single_mx_provider_postmark_exempt(self):
        zone = self._make_valid_mail_zone(
            [{'preference': 10, 'exchange': 'inbound.postmarkapp.com.'}]
        )
        v = MailZoneValidator('test', mode='mail')
        self.assertEqual([], v.validate(zone))

    def test_min_mx_one_disables_redundancy_check(self):
        # min_mx=1 means a single non-exempt MX is fine.
        zone = self._make_valid_mail_zone(
            [{'preference': 10, 'exchange': 'mail1.unit.tests.'}]
        )
        v = MailZoneValidator('test', mode='mail', min_mx=1)
        self.assertEqual([], v.validate(zone))

    def test_min_mx_three_requires_three_values(self):
        # min_mx=3: a two-value MX is now insufficient.
        zone = self._make_valid_mail_zone(
            [
                {'preference': 10, 'exchange': 'mail1.unit.tests.'},
                {'preference': 20, 'exchange': 'mail2.unit.tests.'},
            ]
        )
        v = MailZoneValidator('test', mode='mail', min_mx=3)
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('should have at least 3 values', str(reasons[0]))

    def test_single_mx_regexes_custom_extends_defaults(self):
        # A user-supplied regex exempts a provider not in the built-in list,
        # while the built-in defaults still apply.
        zone = self._make_valid_mail_zone(
            [{'preference': 10, 'exchange': 'mx.customprovider.example.com.'}]
        )
        # Without the custom regex, it is flagged.
        v = MailZoneValidator('test', mode='mail')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('should have at least 2 values', str(reasons[0]))

        # With the custom regex, it is exempt.
        v = MailZoneValidator(
            'test',
            mode='mail',
            single_mx_regexes=[r'\.customprovider\.example\.com\.$'],
        )
        self.assertEqual([], v.validate(zone))

        # Built-in SendGrid exemption still works alongside custom regexes.
        zone2 = self._make_valid_mail_zone(
            [{'preference': 10, 'exchange': 'mx.sendgrid.net.'}]
        )
        self.assertEqual([], v.validate(zone2))

    def test_single_mx_regexes_invalid_pattern_raises(self):
        with self.assertRaisesRegex(ValueError, r'\('):
            MailZoneValidator('test', single_mx_regexes=['('])

    def test_builtin_registration(self):
        ids = [v.id for v in Zone.validators.available_validators()]
        self.assertIn('mail', ids)

    def test_builtins_in_best_practice_set(self):
        Zone.enable_zone_validators({'best-practice'})
        active_ids = [v.id for v in Zone.validators.registered()]
        self.assertIn('mail', active_ids)


class TestMxTargetNotCnameZoneValidator(TestCase):
    def test_empty_zone(self):
        v = MxTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        self.assertEqual([], v.validate(zone))

    def test_out_of_zone_exchange(self):
        v = MxTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail.other.tests.'}],
            },
        )
        zone.add_record(mx)
        self.assertEqual([], v.validate(zone))

    def test_in_zone_exchange_no_cname(self):
        v = MxTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail.unit.tests.'}],
            },
        )
        zone.add_record(mx)
        a = _add_record(zone, 'mail', {'type': 'A', 'values': ['1.2.3.4']})
        zone.add_record(a)
        self.assertEqual([], v.validate(zone))

    def test_in_zone_exchange_is_cname(self):
        v = MxTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail.unit.tests.'}],
            },
        )
        zone.add_record(mx)
        cname = _add_record(
            zone, 'mail', {'type': 'CNAME', 'value': 'real.unit.tests.'}
        )
        zone.add_record(cname)
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('MX record "unit.tests."', str(reasons[0]))
        self.assertIn('mail.unit.tests.', str(reasons[0]))
        self.assertIn('is a CNAME', str(reasons[0]))
        self.assertEqual({mx}, reasons[0].records)

    def test_null_mx_skipped(self):
        v = MxTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {'type': 'MX', 'values': [{'preference': 0, 'exchange': '.'}]},
        )
        zone.add_record(mx)
        self.assertEqual([], v.validate(zone))

    def test_multiple_exchanges_mixed(self):
        v = MxTargetNotCnameZoneValidator('test')
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'type': 'MX',
                'values': [
                    {'preference': 10, 'exchange': 'mail1.unit.tests.'},
                    {'preference': 20, 'exchange': 'mail2.unit.tests.'},
                ],
            },
        )
        zone.add_record(mx)
        cname = _add_record(
            zone, 'mail1', {'type': 'CNAME', 'value': 'real.unit.tests.'}
        )
        zone.add_record(cname)
        a = _add_record(zone, 'mail2', {'type': 'A', 'values': ['1.2.3.4']})
        zone.add_record(a)
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('mail1.unit.tests.', str(reasons[0]))

    def test_builtin_registration(self):
        ids = [v.id for v in Zone.validators.available_validators()]
        self.assertIn('mx-target-not-cname', ids)

    def test_builtins_in_strict_set(self):
        Zone.enable_zone_validators({'strict'})
        active_ids = [v.id for v in Zone.validators.registered()]
        self.assertIn('mx-target-not-cname', active_ids)


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
