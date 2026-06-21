#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record.base import Record
from octodns.record.exception import ValidationError
from octodns.record.rr import RrParseError
from octodns.record.sshfp import (
    SshfpRecord,
    SshfpValue,
    SshfpValueBestPracticeValidator,
    SshfpValueRfcValidator,
)
from octodns.zone import Zone


class TestRecordSshfp(TestCase):
    zone = Zone('unit.tests.', [])

    def test_sshfp(self):
        a_values = [
            SshfpValue(
                {
                    'algorithm': 10,
                    'fingerprint_type': 11,
                    'fingerprint': 'abc123',
                }
            ),
            SshfpValue(
                {
                    'algorithm': 20,
                    'fingerprint_type': 21,
                    'fingerprint': 'def456',
                }
            ),
        ]
        a_data = {'ttl': 30, 'values': a_values}
        a = SshfpRecord(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values[0]['algorithm'], a.values[0].algorithm)
        self.assertEqual(
            a_values[0]['fingerprint_type'], a.values[0].fingerprint_type
        )
        self.assertEqual(a_values[0]['fingerprint'], a.values[0].fingerprint)
        self.assertEqual(a_data, a.data)

        b_value = SshfpValue(
            {'algorithm': 30, 'fingerprint_type': 31, 'fingerprint': 'ghi789'}
        )
        b_data = {'ttl': 30, 'value': b_value}
        b = SshfpRecord(self.zone, 'b', b_data)
        self.assertEqual(b_value['algorithm'], b.values[0].algorithm)
        self.assertEqual(
            b_value['fingerprint_type'], b.values[0].fingerprint_type
        )
        self.assertEqual(b_value['fingerprint'], b.values[0].fingerprint)
        self.assertEqual(b_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in algorithm causes change
        other = SshfpRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].algorithm = 22
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in fingerprint_type causes change
        other = SshfpRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].algorithm = a.values[0].algorithm
        other.values[0].fingerprint_type = 22
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in fingerprint causes change
        other = SshfpRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].fingerprint_type = a.values[0].fingerprint_type
        other.values[0].fingerprint = 22
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_sshfp_value_rdata_text(self):
        # empty string won't parse
        with self.assertRaises(RrParseError):
            SshfpValue.parse_rdata_text('')

        # single word won't parse
        with self.assertRaises(RrParseError):
            SshfpValue.parse_rdata_text('nope')

        # 3rd word won't parse
        with self.assertRaises(RrParseError):
            SshfpValue.parse_rdata_text('0 1 00479b27 another')

        # algorithm and fingerprint_type not ints
        self.assertEqual(
            {
                'algorithm': 'one',
                'fingerprint_type': 'two',
                'fingerprint': '00479b27',
            },
            SshfpValue.parse_rdata_text('one two 00479b27'),
        )

        # valid
        self.assertEqual(
            {'algorithm': 1, 'fingerprint_type': 2, 'fingerprint': '00479b27'},
            SshfpValue.parse_rdata_text('1 2 00479b27'),
        )

        # valid
        self.assertEqual(
            {'algorithm': 1, 'fingerprint_type': 2, 'fingerprint': '00479b27'},
            SshfpValue.parse_rdata_text('1 2 "00479b27"'),
        )

        zone = Zone('unit.tests.', [])
        a = SshfpRecord(
            zone,
            'sshfp',
            {
                'ttl': 32,
                'value': {
                    'algorithm': 1,
                    'fingerprint_type': 2,
                    'fingerprint': '00479b27',
                },
            },
        )
        self.assertEqual(1, a.values[0].algorithm)
        self.assertEqual(2, a.values[0].fingerprint_type)
        self.assertEqual('00479b27', a.values[0].fingerprint)
        self.assertEqual('1 2 00479b27', a.values[0].rdata_text)

    def test_sshfp_value(self):
        a = SshfpValue(
            {'algorithm': 0, 'fingerprint_type': 0, 'fingerprint': 'abcd'}
        )
        b = SshfpValue(
            {'algorithm': 1, 'fingerprint_type': 0, 'fingerprint': 'abcd'}
        )
        c = SshfpValue(
            {'algorithm': 0, 'fingerprint_type': 1, 'fingerprint': 'abcd'}
        )
        d = SshfpValue(
            {'algorithm': 0, 'fingerprint_type': 0, 'fingerprint': 'bcde'}
        )

        self.assertEqual(a, a)
        self.assertEqual(b, b)
        self.assertEqual(c, c)
        self.assertEqual(d, d)

        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(a, d)
        self.assertNotEqual(b, a)
        self.assertNotEqual(b, c)
        self.assertNotEqual(b, d)
        self.assertNotEqual(c, a)
        self.assertNotEqual(c, b)
        self.assertNotEqual(c, d)
        self.assertNotEqual(d, a)
        self.assertNotEqual(d, b)
        self.assertNotEqual(d, c)

        self.assertTrue(a < b)
        self.assertTrue(a < c)

        self.assertTrue(b > a)
        self.assertTrue(b > c)

        self.assertTrue(c > a)
        self.assertTrue(c < b)

        self.assertTrue(a <= b)
        self.assertTrue(a <= c)
        self.assertTrue(a <= a)
        self.assertTrue(a >= a)

        self.assertTrue(b >= a)
        self.assertTrue(b >= c)
        self.assertTrue(b >= b)
        self.assertTrue(b <= b)

        self.assertTrue(c >= a)
        self.assertTrue(c <= b)
        self.assertTrue(c >= c)
        self.assertTrue(c <= c)

        # Hash
        values = set()
        values.add(a)
        self.assertIn(a, values)
        self.assertNotIn(b, values)
        values.add(b)
        self.assertIn(b, values)

    def test_validation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            '',
            {
                'type': 'SSHFP',
                'ttl': 600,
                'value': {
                    'algorithm': 1,
                    'fingerprint_type': 1,
                    'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                },
            },
        )

        # missing algorithm
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'fingerprint_type': 1,
                        'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                    },
                },
            )
        self.assertEqual(['missing algorithm'], ctx.exception.reasons)

        # invalid algorithm
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'algorithm': 'nope',
                        'fingerprint_type': 1,
                        'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                    },
                },
            )
        self.assertEqual(['invalid algorithm "nope"'], ctx.exception.reasons)

        # unrecognized algorithm
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'algorithm': 42,
                        'fingerprint_type': 1,
                        'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                    },
                },
            )
        self.assertEqual(['unrecognized algorithm "42"'], ctx.exception.reasons)

        # missing fingerprint_type
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'algorithm': 2,
                        'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                    },
                },
            )
        self.assertEqual(['missing fingerprint_type'], ctx.exception.reasons)

        # invalid fingerprint_type
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'algorithm': 3,
                        'fingerprint_type': 'yeeah',
                        'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                    },
                },
            )
        self.assertEqual(
            ['invalid fingerprint_type "yeeah"'], ctx.exception.reasons
        )

        # unrecognized fingerprint_type
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'algorithm': 1,
                        'fingerprint_type': 42,
                        'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                    },
                },
            )
        self.assertEqual(
            ['unrecognized fingerprint_type "42"'], ctx.exception.reasons
        )

        # missing fingerprint
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {'algorithm': 1, 'fingerprint_type': 1},
                },
            )
        self.assertEqual(['missing fingerprint'], ctx.exception.reasons)

        # SHA-1 fingerprint_type with a too-long (64-char) fingerprint
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'algorithm': 1,
                        'fingerprint_type': 1,
                        'fingerprint': 'a' * 64,
                    },
                },
            )
        self.assertEqual(
            [
                'fingerprint length 64 does not match fingerprint_type 1 '
                '(expected 40)'
            ],
            ctx.exception.reasons,
        )

        # SHA-256 fingerprint_type with a 40-char SHA-1 fingerprint — the
        # scenario reported in issue #1371
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'algorithm': 1,
                        'fingerprint_type': 2,
                        'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                    },
                },
            )
        self.assertEqual(
            [
                'fingerprint length 40 does not match fingerprint_type 2 '
                '(expected 64)'
            ],
            ctx.exception.reasons,
        )

        # Valid SHA-256 — happy path, no reasons
        Record.new(
            self.zone,
            '',
            {
                'type': 'SSHFP',
                'ttl': 600,
                'value': {
                    'algorithm': 1,
                    'fingerprint_type': 2,
                    'fingerprint': (
                        '1111111111111111111111111111111111111111'
                        '111111111111111111111111'
                    ),
                },
            },
        )

    def test_rfc_value_validator_not_in_defaults(self):
        registered = Record.registered_validators()
        sshfp_value_ids = set(
            v.id for v in registered['value'].get('SSHFP', [])
        )
        self.assertNotIn('sshfp-value-rfc', sshfp_value_ids)

    def test_value_rfc_validator(self):
        validate = SshfpValueRfcValidator('sshfp-value-rfc').validate

        sha1_fp = 'bf6b6825d2977c511a475bbefb88aad54a92ac73'
        sha256_fp = (
            'a87f1b687ac0e57d2a081a2f282672334d90ed316d2b818ca9580ea384d92401'
        )

        # valid: SHA-1
        self.assertEqual(
            [],
            validate(
                SshfpValue,
                [
                    {
                        'algorithm': 1,
                        'fingerprint_type': 1,
                        'fingerprint': sha1_fp,
                    }
                ],
                'SSHFP',
            ),
        )

        # valid: SHA-256
        self.assertEqual(
            [],
            validate(
                SshfpValue,
                [
                    {
                        'algorithm': 2,
                        'fingerprint_type': 2,
                        'fingerprint': sha256_fp,
                    }
                ],
                'SSHFP',
            ),
        )

        # valid: unknown fingerprint_type — no length check applied
        self.assertEqual(
            [],
            validate(
                SshfpValue,
                [
                    {
                        'algorithm': 4,
                        'fingerprint_type': 3,
                        'fingerprint': sha1_fp,
                    }
                ],
                'SSHFP',
            ),
        )

        # algorithm out of range
        self.assertEqual(
            ['invalid algorithm "256"; must be 0-255'],
            validate(
                SshfpValue,
                [
                    {
                        'algorithm': 256,
                        'fingerprint_type': 1,
                        'fingerprint': sha1_fp,
                    }
                ],
                'SSHFP',
            ),
        )

        # fingerprint_type out of range
        self.assertEqual(
            ['invalid fingerprint_type "300"; must be 0-255'],
            validate(
                SshfpValue,
                [
                    {
                        'algorithm': 1,
                        'fingerprint_type': 300,
                        'fingerprint': sha1_fp,
                    }
                ],
                'SSHFP',
            ),
        )

        # algorithm non-integer
        self.assertEqual(
            ['invalid algorithm "nope"'],
            validate(
                SshfpValue,
                [
                    {
                        'algorithm': 'nope',
                        'fingerprint_type': 1,
                        'fingerprint': sha1_fp,
                    }
                ],
                'SSHFP',
            ),
        )

        # fingerprint_type non-integer
        self.assertEqual(
            ['invalid fingerprint_type "bad"'],
            validate(
                SshfpValue,
                [
                    {
                        'algorithm': 1,
                        'fingerprint_type': 'bad',
                        'fingerprint': sha1_fp,
                    }
                ],
                'SSHFP',
            ),
        )

        # fingerprint not hex
        self.assertEqual(
            ['invalid fingerprint "notahex!!"; must be hex'],
            validate(
                SshfpValue,
                [
                    {
                        'algorithm': 1,
                        'fingerprint_type': 1,
                        'fingerprint': 'notahex!!',
                    }
                ],
                'SSHFP',
            ),
        )

        # SHA-1 fingerprint wrong length (too short)
        self.assertEqual(
            ['fingerprint must be 40 hex characters for fingerprint_type 1'],
            validate(
                SshfpValue,
                [
                    {
                        'algorithm': 1,
                        'fingerprint_type': 1,
                        'fingerprint': sha256_fp,
                    }
                ],
                'SSHFP',
            ),
        )

        # SHA-256 fingerprint wrong length (too short)
        self.assertEqual(
            ['fingerprint must be 64 hex characters for fingerprint_type 2'],
            validate(
                SshfpValue,
                [
                    {
                        'algorithm': 2,
                        'fingerprint_type': 2,
                        'fingerprint': sha1_fp,
                    }
                ],
                'SSHFP',
            ),
        )

        # missing all fields
        self.assertEqual(
            [
                'missing algorithm',
                'missing fingerprint_type',
                'missing fingerprint',
            ],
            validate(SshfpValue, [{}], 'SSHFP'),
        )

    def test_rfc_value_validator_opt_in(self):
        zone = Zone('unit.tests.', [])
        Record.enable_validators(['legacy'])
        Record.enable_validator('sshfp-value-rfc', types=['SSHFP'])
        try:
            # right length for SHA-1 but non-hex chars — only RFC validator catches
            with self.assertRaises(ValidationError) as ctx:
                Record.new(
                    zone,
                    '',
                    {
                        'type': 'SSHFP',
                        'ttl': 600,
                        'value': {
                            'algorithm': 1,
                            'fingerprint_type': 1,
                            'fingerprint': 'z' * 40,
                        },
                    },
                )
            self.assertEqual(
                [f'invalid fingerprint "{"z" * 40}"; must be hex'],
                ctx.exception.reasons,
            )
            # valid: SHA-1 passes
            Record.new(
                zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'algorithm': 1,
                        'fingerprint_type': 1,
                        'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                    },
                },
            )
        finally:
            Record.disable_validator('sshfp-value-rfc', types=['SSHFP'])

    def test_fingerprint_case_insensitive(self):
        target = SimpleProvider()

        # uppercase input is normalized to lowercase
        upper = Record.new(
            self.zone,
            '',
            {
                'type': 'SSHFP',
                'ttl': 600,
                'value': {
                    'algorithm': 1,
                    'fingerprint_type': 1,
                    'fingerprint': 'BF6B6825D2977C511A475BBEFB88AAD54A92AC73',
                },
            },
        )
        self.assertEqual(
            'bf6b6825d2977c511a475bbefb88aad54a92ac73',
            upper.values[0].fingerprint,
        )

        # same value in lowercase — no change detected
        lower = Record.new(
            self.zone,
            '',
            {
                'type': 'SSHFP',
                'ttl': 600,
                'value': {
                    'algorithm': 1,
                    'fingerprint_type': 1,
                    'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                },
            },
        )
        self.assertFalse(upper.changes(lower, target))
        self.assertFalse(lower.changes(upper, target))


class TestSshfpBestPractice(TestCase):

    def test_best_practice_validator(self):
        validate = SshfpValueBestPracticeValidator(
            'sshfp-value-best-practice'
        ).validate

        sha1_fp = 'bf6b6825d2977c511a475bbefb88aad54a92ac73'
        sha256_fp = (
            'a87f1b687ac0e57d2a081a2f282672334d90ed316d2b818ca9580ea384d92401'
        )

        # SHA-256 fingerprint_type passes
        self.assertEqual(
            [],
            validate(
                SshfpValue,
                [
                    {
                        'algorithm': 1,
                        'fingerprint_type': 2,
                        'fingerprint': sha256_fp,
                    }
                ],
                'SSHFP',
            ),
        )
        # unknown fingerprint_type passes (not our concern)
        self.assertEqual(
            [],
            validate(
                SshfpValue,
                [
                    {
                        'algorithm': 4,
                        'fingerprint_type': 3,
                        'fingerprint': sha1_fp,
                    }
                ],
                'SSHFP',
            ),
        )
        # missing fingerprint_type — no error (format validator handles it)
        self.assertEqual(
            [],
            validate(
                SshfpValue, [{'algorithm': 1, 'fingerprint': sha1_fp}], 'SSHFP'
            ),
        )
        # SHA-1 fingerprint_type triggers warning
        self.assertEqual(
            [
                'SSHFP fingerprint_type 1 (SHA-1) is deprecated; '
                'use fingerprint_type 2 (SHA-256)'
            ],
            validate(
                SshfpValue,
                [
                    {
                        'algorithm': 1,
                        'fingerprint_type': 1,
                        'fingerprint': sha1_fp,
                    }
                ],
                'SSHFP',
            ),
        )
        # multiple values — each SHA-1 value reported
        self.assertEqual(
            [
                'SSHFP fingerprint_type 1 (SHA-1) is deprecated; '
                'use fingerprint_type 2 (SHA-256)',
                'SSHFP fingerprint_type 1 (SHA-1) is deprecated; '
                'use fingerprint_type 2 (SHA-256)',
            ],
            validate(
                SshfpValue,
                [
                    {
                        'algorithm': 1,
                        'fingerprint_type': 1,
                        'fingerprint': sha1_fp,
                    },
                    {
                        'algorithm': 2,
                        'fingerprint_type': 1,
                        'fingerprint': sha1_fp,
                    },
                ],
                'SSHFP',
            ),
        )

        # opt-in via Record.enable_validator
        zone = Zone('unit.tests.', [])
        Record.enable_validators(['legacy'])
        Record.enable_validator('sshfp-value-best-practice', types=['SSHFP'])
        try:
            with self.assertRaises(ValidationError) as ctx:
                Record.new(
                    zone,
                    '',
                    {
                        'type': 'SSHFP',
                        'ttl': 600,
                        'value': {
                            'algorithm': 1,
                            'fingerprint_type': 1,
                            'fingerprint': sha1_fp,
                        },
                    },
                )
            self.assertEqual(
                [
                    'SSHFP fingerprint_type 1 (SHA-1) is deprecated; '
                    'use fingerprint_type 2 (SHA-256)'
                ],
                ctx.exception.reasons,
            )
            # SHA-256 passes
            Record.new(
                zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'algorithm': 1,
                        'fingerprint_type': 2,
                        'fingerprint': sha256_fp,
                    },
                },
            )
        finally:
            Record.disable_validator(
                'sshfp-value-best-practice', types=['SSHFP']
            )

    def test_best_practice_not_in_defaults(self):
        registered = Record.registered_validators()
        sshfp_value_ids = set(
            v.id for v in registered['value'].get('SSHFP', [])
        )
        self.assertNotIn('sshfp-value-best-practice', sshfp_value_ids)


class TestSshFpValue(TestCase):

    def test_template(self):
        value = SshfpValue(
            {'algorithm': 10, 'fingerprint_type': 11, 'fingerprint': 'abc123'}
        )
        got = value.template({'needle': 42})
        self.assertIs(value, got)

        value = SshfpValue(
            {
                'algorithm': 10,
                'fingerprint_type': 11,
                'fingerprint': 'ab{needle}c123',
            }
        )
        got = value.template({'needle': 42})
        self.assertIsNot(value, got)
        self.assertEqual('ab42c123', got.fingerprint)
