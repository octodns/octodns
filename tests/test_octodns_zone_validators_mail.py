#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.mail import MailZoneValidator


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
        # The Null MX has exactly 1 value by design, which always triggers the
        # MX redundancy check; no-mail-specific validations all pass.
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn(
            'should have at least 2 values for redundancy', str(reasons[0])
        )

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

        # Auto-detects 'no-mail' via Null MX; redundancy check fires first
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
        self.assertIn(
            'should have at least 2 values for redundancy', str(reasons[0])
        )
        self.assertIn('missing strict SPF TXT record', str(reasons[1]))

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

        # Non-apex MX alone does NOT trigger mail mode detection; only the
        # redundancy check fires, not full mail/no-mail validation.
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
        self.assertEqual(1, len(reasons))
        self.assertIn(
            'should have at least 2 values for redundancy', str(reasons[0])
        )

        # No-op with no signs
        zone = _make_zone()
        self.assertEqual([], v.validate(zone))

    def test_builtin_registration(self):
        ids = [v.id for v in Zone.validators.available_validators()]
        self.assertIn('mail', ids)

    def test_builtins_in_best_practice_set(self):
        Zone.enable_zone_validators({'best-practice'})
        active_ids = [v.id for v in Zone.validators.registered()]
        self.assertIn('mail', active_ids)
