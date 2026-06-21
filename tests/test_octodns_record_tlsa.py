#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.rr import RrParseError
from octodns.record.tlsa import (
    TlsaRecord,
    TlsaValue,
    TlsaValueBestPracticeValidator,
    TlsaValueRfcValidator,
)
from octodns.zone import Zone


class TestRecordTlsa(TestCase):
    zone = Zone('unit.tests.', [])

    def test_tlsa(self):
        a_values = [
            TlsaValue(
                {
                    'certificate_usage': 1,
                    'selector': 1,
                    'matching_type': 1,
                    'certificate_association_data': 'ABABABABABABABABAB',
                }
            ),
            TlsaValue(
                {
                    'certificate_usage': 2,
                    'selector': 0,
                    'matching_type': 2,
                    'certificate_association_data': 'ABABABABABABABABAC',
                }
            ),
        ]
        a_data = {'ttl': 30, 'values': a_values}
        a = TlsaRecord(self.zone, 'a', a_data)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual('a', a.name)
        self.assertEqual(30, a.ttl)
        self.assertEqual(
            a_values[0]['certificate_usage'], a.values[0].certificate_usage
        )
        self.assertEqual(a_values[0]['selector'], a.values[0].selector)
        self.assertEqual(
            a_values[0]['matching_type'], a.values[0].matching_type
        )
        self.assertEqual(
            a_values[0]['certificate_association_data'],
            a.values[0].certificate_association_data,
        )

        self.assertEqual(
            a_values[1]['certificate_usage'], a.values[1].certificate_usage
        )
        self.assertEqual(a_values[1]['selector'], a.values[1].selector)
        self.assertEqual(
            a_values[1]['matching_type'], a.values[1].matching_type
        )
        self.assertEqual(
            a_values[1]['certificate_association_data'],
            a.values[1].certificate_association_data,
        )
        self.assertEqual(a_data, a.data)

        b_value = TlsaValue(
            {
                'certificate_usage': 0,
                'selector': 0,
                'matching_type': 0,
                'certificate_association_data': 'AAAAAAAAAAAAAAA',
            }
        )
        b_data = {'ttl': 30, 'value': b_value}
        b = TlsaRecord(self.zone, 'b', b_data)
        self.assertEqual(
            b_value['certificate_usage'], b.values[0].certificate_usage
        )
        self.assertEqual(b_value['selector'], b.values[0].selector)
        self.assertEqual(b_value['matching_type'], b.values[0].matching_type)
        self.assertEqual(
            b_value['certificate_association_data'],
            b.values[0].certificate_association_data,
        )
        self.assertEqual(b_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in certificate_usage causes change
        other = TlsaRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].certificate_usage = 0
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in selector causes change
        other = TlsaRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].selector = 0
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in matching_type causes change
        other = TlsaRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].matching_type = 0
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in certificate_association_data causes change
        other = TlsaRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].certificate_association_data = 'AAAAAAAAAAAAA'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_tsla_value_rdata_text(self):
        # empty string won't parse
        with self.assertRaises(RrParseError):
            TlsaValue.parse_rdata_text('')

        # single word won't parse
        with self.assertRaises(RrParseError):
            TlsaValue.parse_rdata_text('nope')

        # 2nd word won't parse
        with self.assertRaises(RrParseError):
            TlsaValue.parse_rdata_text('1 2')

        # 3rd word won't parse
        with self.assertRaises(RrParseError):
            TlsaValue.parse_rdata_text('1 2 3')

        # 5th word won't parse
        with self.assertRaises(RrParseError):
            TlsaValue.parse_rdata_text('1 2 3 abcd another')

        # non-ints
        self.assertEqual(
            {
                'certificate_usage': 'one',
                'selector': 'two',
                'matching_type': 'three',
                'certificate_association_data': 'abcd',
            },
            TlsaValue.parse_rdata_text('one two three abcd'),
        )

        # valid
        self.assertEqual(
            {
                'certificate_usage': 1,
                'selector': 2,
                'matching_type': 3,
                'certificate_association_data': 'abcd',
            },
            TlsaValue.parse_rdata_text('1 2 3 abcd'),
        )

        # valid
        self.assertEqual(
            {
                'certificate_usage': 1,
                'selector': 2,
                'matching_type': 3,
                'certificate_association_data': 'abcd',
            },
            TlsaValue.parse_rdata_text('1 2 3 "abcd"'),
        )

        zone = Zone('unit.tests.', [])
        a = TlsaRecord(
            zone,
            'tlsa',
            {
                'ttl': 32,
                'value': {
                    'certificate_usage': 2,
                    'selector': 1,
                    'matching_type': 0,
                    'certificate_association_data': 'abcd',
                },
            },
        )
        self.assertEqual(2, a.values[0].certificate_usage)
        self.assertEqual(1, a.values[0].selector)
        self.assertEqual(0, a.values[0].matching_type)
        self.assertEqual('abcd', a.values[0].certificate_association_data)
        self.assertEqual('2 1 0 abcd', a.values[0].rdata_text)

    def test_validation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            '',
            {
                'type': 'TLSA',
                'ttl': 600,
                'value': {
                    'certificate_usage': 0,
                    'selector': 0,
                    'matching_type': 0,
                    'certificate_association_data': 'AAAAAAAAAAAAA',
                },
            },
        )
        # Multi value, second missing certificate usage
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'values': [
                        {
                            'certificate_usage': 0,
                            'selector': 0,
                            'matching_type': 0,
                            'certificate_association_data': 'AAAAAAAAAAAAA',
                        },
                        {
                            'selector': 0,
                            'matching_type': 0,
                            'certificate_association_data': 'AAAAAAAAAAAAA',
                        },
                    ],
                },
            )
            self.assertEqual(
                ['missing certificate_usage'], ctx.exception.reasons
            )

        # missing certificate_association_data
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 0,
                        'selector': 0,
                        'matching_type': 0,
                    },
                },
            )
            self.assertEqual(
                ['missing certificate_association_data'], ctx.exception.reasons
            )

        # missing certificate_usage
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'selector': 0,
                        'matching_type': 0,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(
                ['missing certificate_usage'], ctx.exception.reasons
            )

        # False certificate_usage
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 4,
                        'selector': 0,
                        'matching_type': 0,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(
                'invalid certificate_usage "{value["certificate_usage"]}"',
                ctx.exception.reasons,
            )

        # Invalid certificate_usage
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 'XYZ',
                        'selector': 0,
                        'matching_type': 0,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(
                'invalid certificate_usage "{value["certificate_usage"]}"',
                ctx.exception.reasons,
            )

        # missing selector
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 0,
                        'matching_type': 0,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(['missing selector'], ctx.exception.reasons)

        # False selector
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 0,
                        'selector': 4,
                        'matching_type': 0,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(
                'invalid selector "{value["selector"]}"', ctx.exception.reasons
            )

        # Invalid selector
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 0,
                        'selector': 'XYZ',
                        'matching_type': 0,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(
                'invalid selector "{value["selector"]}"', ctx.exception.reasons
            )

        # missing matching_type
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 0,
                        'selector': 0,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(['missing matching_type'], ctx.exception.reasons)

        # False matching_type
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 0,
                        'selector': 1,
                        'matching_type': 3,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(
                'invalid matching_type "{value["matching_type"]}"',
                ctx.exception.reasons,
            )

        # Invalid matching_type
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 0,
                        'selector': 1,
                        'matching_type': 'XYZ',
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(
                'invalid matching_type "{value["matching_type"]}"',
                ctx.exception.reasons,
            )

    def test_certificate_association_data_case_insensitive(self):
        target = SimpleProvider()

        # uppercase input is normalized to lowercase
        upper = TlsaRecord(
            self.zone,
            'a',
            {
                'ttl': 30,
                'value': {
                    'certificate_usage': 3,
                    'selector': 1,
                    'matching_type': 1,
                    'certificate_association_data': 'ABCDEF1234567890',
                },
            },
        )
        self.assertEqual(
            'abcdef1234567890', upper.values[0].certificate_association_data
        )

        # same value in lowercase — no change detected
        lower = TlsaRecord(
            self.zone,
            'a',
            {
                'ttl': 30,
                'value': {
                    'certificate_usage': 3,
                    'selector': 1,
                    'matching_type': 1,
                    'certificate_association_data': 'abcdef1234567890',
                },
            },
        )
        self.assertFalse(upper.changes(lower, target))
        self.assertFalse(lower.changes(upper, target))

    def test_rfc_value_validator_not_in_defaults(self):
        registered = Record.registered_validators()
        tlsa_value_ids = set(v.id for v in registered['value'].get('TLSA', []))
        self.assertNotIn('tlsa-value-rfc', tlsa_value_ids)

    def test_value_rfc_validator(self):
        validate = TlsaValueRfcValidator('tlsa-value-rfc').validate

        sha256 = 'a' * 64
        sha512 = 'b' * 128

        # valid: matching_type 0, any hex data
        self.assertEqual(
            [],
            validate(
                TlsaValue,
                [
                    {
                        'certificate_usage': 3,
                        'selector': 1,
                        'matching_type': 0,
                        'certificate_association_data': 'deadbeef',
                    }
                ],
                'TLSA',
            ),
        )
        # valid: matching_type 1, 64 hex chars
        self.assertEqual(
            [],
            validate(
                TlsaValue,
                [
                    {
                        'certificate_usage': 1,
                        'selector': 0,
                        'matching_type': 1,
                        'certificate_association_data': sha256,
                    }
                ],
                'TLSA',
            ),
        )
        # valid: matching_type 2, 128 hex chars
        self.assertEqual(
            [],
            validate(
                TlsaValue,
                [
                    {
                        'certificate_usage': 0,
                        'selector': 1,
                        'matching_type': 2,
                        'certificate_association_data': sha512,
                    }
                ],
                'TLSA',
            ),
        )

        # invalid certificate_usage (out of uint8 range)
        self.assertEqual(
            ['invalid certificate_usage "256"; must be 0-255'],
            validate(
                TlsaValue,
                [
                    {
                        'certificate_usage': 256,
                        'selector': 0,
                        'matching_type': 0,
                        'certificate_association_data': 'deadbeef',
                    }
                ],
                'TLSA',
            ),
        )

        # invalid selector (non-integer)
        self.assertEqual(
            ['invalid selector "bad"'],
            validate(
                TlsaValue,
                [
                    {
                        'certificate_usage': 0,
                        'selector': 'bad',
                        'matching_type': 0,
                        'certificate_association_data': 'deadbeef',
                    }
                ],
                'TLSA',
            ),
        )

        # invalid matching_type (out of range)
        self.assertEqual(
            ['invalid matching_type "300"; must be 0-255'],
            validate(
                TlsaValue,
                [
                    {
                        'certificate_usage': 0,
                        'selector': 0,
                        'matching_type': 300,
                        'certificate_association_data': 'deadbeef',
                    }
                ],
                'TLSA',
            ),
        )

        # invalid certificate_association_data (not hex)
        self.assertEqual(
            ['invalid certificate_association_data "notahex"; must be hex'],
            validate(
                TlsaValue,
                [
                    {
                        'certificate_usage': 0,
                        'selector': 0,
                        'matching_type': 0,
                        'certificate_association_data': 'notahex',
                    }
                ],
                'TLSA',
            ),
        )

        # matching_type 1 with wrong length
        self.assertEqual(
            [
                'certificate_association_data must be 64 hex characters for matching_type 1'
            ],
            validate(
                TlsaValue,
                [
                    {
                        'certificate_usage': 0,
                        'selector': 0,
                        'matching_type': 1,
                        'certificate_association_data': 'deadbeef',
                    }
                ],
                'TLSA',
            ),
        )

        # matching_type 2 with wrong length
        self.assertEqual(
            [
                'certificate_association_data must be 128 hex characters for matching_type 2'
            ],
            validate(
                TlsaValue,
                [
                    {
                        'certificate_usage': 0,
                        'selector': 0,
                        'matching_type': 2,
                        'certificate_association_data': sha256,
                    }
                ],
                'TLSA',
            ),
        )

        # missing fields
        self.assertEqual(
            [
                'missing certificate_usage',
                'missing selector',
                'missing matching_type',
                'missing certificate_association_data',
            ],
            validate(TlsaValue, [{}], 'TLSA'),
        )

    def test_rfc_value_validator_opt_in(self):
        zone = Zone('unit.tests.', [])
        Record.enable_validators(['legacy'])
        Record.enable_validator('tlsa-value-rfc', types=['TLSA'])
        sha256 = 'a' * 64
        try:
            # non-hex certificate_association_data
            with self.assertRaises(ValidationError) as ctx:
                Record.new(
                    zone,
                    '',
                    {
                        'type': 'TLSA',
                        'ttl': 600,
                        'value': {
                            'certificate_usage': 3,
                            'selector': 1,
                            'matching_type': 1,
                            'certificate_association_data': 'notahex',
                        },
                    },
                )
            self.assertIn(
                'invalid certificate_association_data "notahex"; must be hex',
                ctx.exception.reasons,
            )
            # wrong length for SHA-256
            with self.assertRaises(ValidationError) as ctx:
                Record.new(
                    zone,
                    '',
                    {
                        'type': 'TLSA',
                        'ttl': 600,
                        'value': {
                            'certificate_usage': 3,
                            'selector': 1,
                            'matching_type': 1,
                            'certificate_association_data': 'deadbeef',
                        },
                    },
                )
            self.assertIn(
                'certificate_association_data must be 64 hex characters for matching_type 1',
                ctx.exception.reasons,
            )
            # valid passes
            Record.new(
                zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 3,
                        'selector': 1,
                        'matching_type': 1,
                        'certificate_association_data': sha256,
                    },
                },
            )
        finally:
            Record.disable_validator('tlsa-value-rfc', types=['TLSA'])


class TestTlsaBestPractice(TestCase):

    def test_best_practice_validator(self):
        validate = TlsaValueBestPracticeValidator(
            'tlsa-value-best-practice'
        ).validate

        cad = 'a' * 64

        # matching_type 1 (SHA-256) passes
        self.assertEqual(
            [],
            validate(
                TlsaValue,
                [
                    {
                        'certificate_usage': 3,
                        'selector': 1,
                        'matching_type': 1,
                        'certificate_association_data': cad,
                    }
                ],
                'TLSA',
            ),
        )
        # matching_type 2 (SHA-512) passes
        self.assertEqual(
            [],
            validate(
                TlsaValue,
                [
                    {
                        'certificate_usage': 3,
                        'selector': 1,
                        'matching_type': 2,
                        'certificate_association_data': cad,
                    }
                ],
                'TLSA',
            ),
        )
        # missing matching_type — no error (format validator handles it)
        self.assertEqual(
            [],
            validate(
                TlsaValue,
                [
                    {
                        'certificate_usage': 3,
                        'selector': 1,
                        'certificate_association_data': cad,
                    }
                ],
                'TLSA',
            ),
        )
        # matching_type 0 (full data) triggers warning
        self.assertEqual(
            [
                'TLSA matching_type 0 (full data) is not recommended; '
                'use matching_type 1 (SHA-256) or 2 (SHA-512)'
            ],
            validate(
                TlsaValue,
                [
                    {
                        'certificate_usage': 3,
                        'selector': 1,
                        'matching_type': 0,
                        'certificate_association_data': cad,
                    }
                ],
                'TLSA',
            ),
        )
        # multiple values — each matching_type 0 is reported
        self.assertEqual(
            [
                'TLSA matching_type 0 (full data) is not recommended; '
                'use matching_type 1 (SHA-256) or 2 (SHA-512)',
                'TLSA matching_type 0 (full data) is not recommended; '
                'use matching_type 1 (SHA-256) or 2 (SHA-512)',
            ],
            validate(
                TlsaValue,
                [
                    {
                        'certificate_usage': 3,
                        'selector': 1,
                        'matching_type': 0,
                        'certificate_association_data': cad,
                    },
                    {
                        'certificate_usage': 1,
                        'selector': 0,
                        'matching_type': 0,
                        'certificate_association_data': cad,
                    },
                ],
                'TLSA',
            ),
        )

        # opt-in via Record.enable_validator
        zone = Zone('unit.tests.', [])
        Record.enable_validators(['legacy'])
        Record.enable_validator('tlsa-value-best-practice', types=['TLSA'])
        try:
            with self.assertRaises(ValidationError) as ctx:
                Record.new(
                    zone,
                    '_443._tcp',
                    {
                        'type': 'TLSA',
                        'ttl': 600,
                        'value': {
                            'certificate_usage': 3,
                            'selector': 1,
                            'matching_type': 0,
                            'certificate_association_data': cad,
                        },
                    },
                )
            self.assertEqual(
                [
                    'TLSA matching_type 0 (full data) is not recommended; '
                    'use matching_type 1 (SHA-256) or 2 (SHA-512)'
                ],
                ctx.exception.reasons,
            )
            # matching_type 1 passes
            Record.new(
                zone,
                '_443._tcp',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 3,
                        'selector': 1,
                        'matching_type': 1,
                        'certificate_association_data': cad,
                    },
                },
            )
        finally:
            Record.disable_validator('tlsa-value-best-practice', types=['TLSA'])

    def test_best_practice_not_in_defaults(self):
        registered = Record.registered_validators()
        tlsa_value_ids = set(v.id for v in registered['value'].get('TLSA', []))
        self.assertNotIn('tlsa-value-best-practice', tlsa_value_ids)


class TestTlsaValue(TestCase):

    def test_template(self):
        value = TlsaValue(
            {
                'certificate_usage': 1,
                'selector': 1,
                'matching_type': 1,
                'certificate_association_data': 'ABABABABABABABABAB',
            }
        )
        got = value.template({'needle': 42})
        self.assertIs(value, got)

        value = TlsaValue(
            {
                'certificate_usage': 1,
                'selector': 1,
                'matching_type': 1,
                'certificate_association_data': 'ABAB{needle}ABABABABABABAB',
            }
        )
        got = value.template({'needle': 42})
        self.assertIsNot(value, got)
        self.assertEqual(
            'abab42ababababababab', got.certificate_association_data
        )
