#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.record.base import _process_value_validators
from octodns.record.ds import DsRecord, DsValue, DsValueRfcValidator
from octodns.record.exception import ValidationError
from octodns.record.rr import RrParseError
from octodns.zone import Zone


class TestRecordDs(TestCase):
    def test_ds(self):
        for a, b in (
            # diff key_tag
            (
                {
                    'key_tag': 0,
                    'algorithm': 1,
                    'digest_type': 2,
                    'digest': 'abcdef0123456',
                },
                {
                    'key_tag': 1,
                    'algorithm': 1,
                    'digest_type': 2,
                    'digest': 'abcdef0123456',
                },
            ),
            # diff algorithm
            (
                {
                    'key_tag': 0,
                    'algorithm': 1,
                    'digest_type': 2,
                    'digest': 'abcdef0123456',
                },
                {
                    'key_tag': 0,
                    'algorithm': 2,
                    'digest_type': 2,
                    'digest': 'abcdef0123456',
                },
            ),
            # diff digest_type
            (
                {
                    'key_tag': 0,
                    'algorithm': 1,
                    'digest_type': 2,
                    'digest': 'abcdef0123456',
                },
                {
                    'key_tag': 0,
                    'algorithm': 1,
                    'digest_type': 3,
                    'digest': 'abcdef0123456',
                },
            ),
            # diff digest
            (
                {
                    'key_tag': 0,
                    'algorithm': 1,
                    'digest_type': 2,
                    'digest': 'abcdef0123456',
                },
                {
                    'key_tag': 0,
                    'algorithm': 1,
                    'digest_type': 2,
                    'digest': 'bcdef0123456a',
                },
            ),
            # diff digest with previously used key names
            (
                {
                    'flags': 0,
                    'protocol': 1,
                    'algorithm': 2,
                    'public_key': 'abcdef0123456',
                },
                {
                    'key_tag': 0,
                    'algorithm': 1,
                    'digest_type': 2,
                    'digest': 'bcdef0123456a',
                },
            ),
        ):
            a = DsValue(a)
            self.assertEqual(a, a)
            b = DsValue(b)
            self.assertEqual(b, b)
            self.assertNotEqual(a, b)
            self.assertNotEqual(b, a)
            self.assertTrue(a < b)

        # empty string won't parse
        with self.assertRaises(RrParseError):
            DsValue.parse_rdata_text('')

        # single word won't parse
        with self.assertRaises(RrParseError):
            DsValue.parse_rdata_text('nope')

        # 2nd word won't parse
        with self.assertRaises(RrParseError):
            DsValue.parse_rdata_text('0 1')

        # 3rd word won't parse
        with self.assertRaises(RrParseError):
            DsValue.parse_rdata_text('0 1 2')

        # 5th word won't parse
        with self.assertRaises(RrParseError):
            DsValue.parse_rdata_text('0 1 2 key blah')

        # things ints, will parse
        self.assertEqual(
            {
                'key_tag': 'one',
                'algorithm': 'two',
                'digest_type': 'three',
                'digest': 'key',
            },
            DsValue.parse_rdata_text('one two three key'),
        )

        # valid
        data = {
            'key_tag': 0,
            'algorithm': 1,
            'digest_type': 2,
            'digest': '99148c81',
        }
        self.assertEqual(data, DsValue.parse_rdata_text('0 1 2 99148c81'))
        self.assertEqual([], _process_value_validators(DsValue, data, 'DS'))

        # missing key_tag
        data = {'algorithm': 1, 'digest_type': 2, 'digest': '99148c81'}
        self.assertEqual(
            ['missing key_tag'], _process_value_validators(DsValue, data, 'DS')
        )
        # invalid key_tag
        data = {
            'key_tag': 'a',
            'algorithm': 1,
            'digest_type': 2,
            'digest': '99148c81',
        }
        self.assertEqual(
            ['invalid key_tag "a"'],
            _process_value_validators(DsValue, data, 'DS'),
        )

        # missing algorithm
        data = {'key_tag': 1, 'digest_type': 2, 'digest': '99148c81'}
        self.assertEqual(
            ['missing algorithm'],
            _process_value_validators(DsValue, data, 'DS'),
        )
        # invalid algorithm
        data = {
            'key_tag': 1,
            'algorithm': 'a',
            'digest_type': 2,
            'digest': '99148c81',
        }
        self.assertEqual(
            ['invalid algorithm "a"'],
            _process_value_validators(DsValue, data, 'DS'),
        )

        # missing digest_type
        data = {'key_tag': 1, 'algorithm': 2, 'digest': '99148c81'}
        self.assertEqual(
            ['missing digest_type'],
            _process_value_validators(DsValue, data, 'DS'),
        )
        # invalid digest_type
        data = {
            'key_tag': 1,
            'algorithm': 2,
            'digest_type': 'a',
            'digest': '99148c81',
        }
        self.assertEqual(
            ['invalid digest_type "a"'],
            _process_value_validators(DsValue, data, 'DS'),
        )

        # missing public_key (list)
        data = {'key_tag': 1, 'algorithm': 2, 'digest_type': 3}
        self.assertEqual(
            ['missing digest'], _process_value_validators(DsValue, [data], 'DS')
        )

        # do validations again with old field style

        # missing flags (list)
        data = {'protocol': 2, 'algorithm': 3, 'public_key': '99148c81'}
        self.assertEqual(
            ['missing flags'], _process_value_validators(DsValue, [data], 'DS')
        )

        # missing protocol (list)
        data = {'flags': 1, 'algorithm': 3, 'public_key': '99148c81'}
        self.assertEqual(
            ['missing protocol'],
            _process_value_validators(DsValue, [data], 'DS'),
        )

        # missing algorithm (list)
        data = {'flags': 1, 'protocol': 2, 'public_key': '99148c81'}
        self.assertEqual(
            ['missing algorithm'],
            _process_value_validators(DsValue, [data], 'DS'),
        )

        # missing public_key (list)
        data = {'flags': 1, 'algorithm': 3, 'protocol': 2}
        self.assertEqual(
            ['missing public_key'],
            _process_value_validators(DsValue, [data], 'DS'),
        )

        # missing public_key (list)
        data = {'flags': 1, 'algorithm': 3, 'protocol': 2, 'digest': '99148c81'}
        self.assertEqual(
            ['missing public_key'],
            _process_value_validators(DsValue, [data], 'DS'),
        )

        # invalid flags, protocol and algorithm
        data = {
            'flags': 'a',
            'protocol': 'a',
            'algorithm': 'a',
            'public_key': '99148c81',
        }
        self.assertEqual(
            [
                'invalid flags "a"',
                'invalid protocol "a"',
                'invalid algorithm "a"',
            ],
            _process_value_validators(DsValue, data, 'DS'),
        )

        zone = Zone('unit.tests.', [])
        values = [
            {
                'key_tag': 0,
                'algorithm': 1,
                'digest_type': 2,
                'digest': '99148c81',
            },
            {
                'flags': 1,
                'protocol': 2,
                'algorithm': 3,
                'public_key': '99148c44',
            },
        ]
        a = DsRecord(zone, 'ds', {'ttl': 32, 'values': values})
        self.assertEqual(0, a.values[0].key_tag)
        a.values[0].key_tag += 1
        self.assertEqual(1, a.values[0].key_tag)

        self.assertEqual(1, a.values[0].algorithm)
        a.values[0].algorithm += 1
        self.assertEqual(2, a.values[0].algorithm)

        self.assertEqual(2, a.values[0].digest_type)
        a.values[0].digest_type += 1
        self.assertEqual(3, a.values[0].digest_type)

        self.assertEqual('99148c81', a.values[0].digest)
        a.values[0].digest = '99148c42'
        self.assertEqual('99148c42', a.values[0].digest)

        self.assertEqual(1, a.values[1].key_tag)
        self.assertEqual(2, a.values[1].algorithm)
        self.assertEqual(3, a.values[1].digest_type)
        self.assertEqual('99148c44', a.values[1].digest)

        self.assertEqual(DsValue(values[1]), a.values[1].data)
        self.assertEqual('1 2 3 99148c44', a.values[1].rdata_text)
        self.assertEqual('1 2 3 99148c44', a.values[1].__repr__())

    def test_digest_case_insensitive(self):
        zone = Zone('unit.tests.', [])

        # uppercase input is normalized to lowercase
        upper = DsRecord(
            zone,
            'ds',
            {
                'ttl': 30,
                'value': {
                    'key_tag': 1,
                    'algorithm': 2,
                    'digest_type': 3,
                    'digest': 'ABCDEF1234567890',
                },
            },
        )
        self.assertEqual('abcdef1234567890', upper.values[0].digest)

        # same value in lowercase normalizes identically
        lower = DsRecord(
            zone,
            'ds',
            {
                'ttl': 30,
                'value': {
                    'key_tag': 1,
                    'algorithm': 2,
                    'digest_type': 3,
                    'digest': 'abcdef1234567890',
                },
            },
        )
        self.assertEqual(upper.values[0].digest, lower.values[0].digest)

        # legacy field names also normalize
        legacy = DsRecord(
            zone,
            'ds',
            {
                'ttl': 30,
                'value': {
                    'flags': 1,
                    'protocol': 2,
                    'algorithm': 3,
                    'public_key': 'ABCDEF1234567890',
                },
            },
        )
        self.assertEqual('abcdef1234567890', legacy.values[0].digest)

    def test_rfc_value_validator_not_in_defaults(self):
        registered = Record.registered_validators()
        ds_value_ids = set(v.id for v in registered['value'].get('DS', []))
        self.assertNotIn('ds-value-rfc', ds_value_ids)

    def test_value_rfc_validator(self):
        validate = DsValueRfcValidator('ds-value-rfc').validate

        sha1 = 'a' * 40
        sha256 = 'b' * 64
        sha384 = 'c' * 96

        # valid: digest_type 0 (no length constraint)
        self.assertEqual(
            [],
            validate(
                DsValue,
                [
                    {
                        'key_tag': 1234,
                        'algorithm': 8,
                        'digest_type': 0,
                        'digest': 'deadbeef',
                    }
                ],
                'DS',
            ),
        )
        # valid: digest_type 1 (SHA-1), 40 hex chars
        self.assertEqual(
            [],
            validate(
                DsValue,
                [
                    {
                        'key_tag': 1,
                        'algorithm': 5,
                        'digest_type': 1,
                        'digest': sha1,
                    }
                ],
                'DS',
            ),
        )
        # valid: digest_type 2 (SHA-256), 64 hex chars
        self.assertEqual(
            [],
            validate(
                DsValue,
                [
                    {
                        'key_tag': 1,
                        'algorithm': 8,
                        'digest_type': 2,
                        'digest': sha256,
                    }
                ],
                'DS',
            ),
        )
        # valid: digest_type 4 (SHA-384), 96 hex chars
        self.assertEqual(
            [],
            validate(
                DsValue,
                [
                    {
                        'key_tag': 1,
                        'algorithm': 14,
                        'digest_type': 4,
                        'digest': sha384,
                    }
                ],
                'DS',
            ),
        )

        # key_tag out of range
        self.assertEqual(
            ['invalid key_tag "70000"; must be 0-65535'],
            validate(
                DsValue,
                [
                    {
                        'key_tag': 70000,
                        'algorithm': 8,
                        'digest_type': 0,
                        'digest': 'deadbeef',
                    }
                ],
                'DS',
            ),
        )

        # key_tag non-integer
        self.assertEqual(
            ['invalid key_tag "nope"'],
            validate(
                DsValue,
                [
                    {
                        'key_tag': 'nope',
                        'algorithm': 8,
                        'digest_type': 0,
                        'digest': 'deadbeef',
                    }
                ],
                'DS',
            ),
        )

        # algorithm out of range
        self.assertEqual(
            ['invalid algorithm "300"; must be 0-255'],
            validate(
                DsValue,
                [
                    {
                        'key_tag': 1,
                        'algorithm': 300,
                        'digest_type': 0,
                        'digest': 'deadbeef',
                    }
                ],
                'DS',
            ),
        )

        # invalid digest (not hex)
        self.assertEqual(
            ['invalid digest "notahex"; must be hex'],
            validate(
                DsValue,
                [
                    {
                        'key_tag': 1,
                        'algorithm': 8,
                        'digest_type': 0,
                        'digest': 'notahex',
                    }
                ],
                'DS',
            ),
        )

        # digest_type 1, wrong length
        self.assertEqual(
            ['digest must be 40 hex characters for digest_type 1'],
            validate(
                DsValue,
                [
                    {
                        'key_tag': 1,
                        'algorithm': 5,
                        'digest_type': 1,
                        'digest': 'deadbeef',
                    }
                ],
                'DS',
            ),
        )

        # digest_type 2, wrong length
        self.assertEqual(
            ['digest must be 64 hex characters for digest_type 2'],
            validate(
                DsValue,
                [
                    {
                        'key_tag': 1,
                        'algorithm': 8,
                        'digest_type': 2,
                        'digest': sha1,
                    }
                ],
                'DS',
            ),
        )

        # digest_type 4, wrong length
        self.assertEqual(
            ['digest must be 96 hex characters for digest_type 4'],
            validate(
                DsValue,
                [
                    {
                        'key_tag': 1,
                        'algorithm': 14,
                        'digest_type': 4,
                        'digest': sha256,
                    }
                ],
                'DS',
            ),
        )

        # missing all fields
        self.assertEqual(
            [
                'missing key_tag',
                'missing algorithm',
                'missing digest_type',
                'missing digest',
            ],
            validate(DsValue, [{}], 'DS'),
        )

        # accepts list or single value
        self.assertEqual(
            [],
            validate(
                DsValue,
                {
                    'key_tag': 1,
                    'algorithm': 8,
                    'digest_type': 0,
                    'digest': 'deadbeef',
                },
                'DS',
            ),
        )

    def test_rfc_value_validator_opt_in(self):
        zone = Zone('unit.tests.', [])
        Record.enable_validators(['legacy'])
        Record.enable_validator('ds-value-rfc', types=['DS'])
        sha256 = 'a' * 64
        try:
            # non-hex digest
            with self.assertRaises(ValidationError) as ctx:
                Record.new(
                    zone,
                    '',
                    {
                        'type': 'DS',
                        'ttl': 600,
                        'value': {
                            'key_tag': 1234,
                            'algorithm': 8,
                            'digest_type': 2,
                            'digest': 'notahex',
                        },
                    },
                )
            self.assertIn(
                'invalid digest "notahex"; must be hex', ctx.exception.reasons
            )
            # wrong length for SHA-256
            with self.assertRaises(ValidationError) as ctx:
                Record.new(
                    zone,
                    '',
                    {
                        'type': 'DS',
                        'ttl': 600,
                        'value': {
                            'key_tag': 1234,
                            'algorithm': 8,
                            'digest_type': 2,
                            'digest': 'deadbeef',
                        },
                    },
                )
            self.assertIn(
                'digest must be 64 hex characters for digest_type 2',
                ctx.exception.reasons,
            )
            # valid passes
            Record.new(
                zone,
                '',
                {
                    'type': 'DS',
                    'ttl': 600,
                    'value': {
                        'key_tag': 1234,
                        'algorithm': 8,
                        'digest_type': 2,
                        'digest': sha256,
                    },
                },
            )
        finally:
            Record.disable_validator('ds-value-rfc', types=['DS'])


class TestDsValue(TestCase):

    def test_template(self):
        value = DsValue(
            {
                'key_tag': 0,
                'algorithm': 1,
                'digest_type': 2,
                'digest': 'abcdef0123456',
            }
        )
        got = value.template({'needle': 42})
        self.assertIs(value, got)

        value = DsValue(
            {
                'key_tag': 0,
                'algorithm': 1,
                'digest_type': 2,
                'digest': 'abcd{needle}ef0123456',
            }
        )
        got = value.template({'needle': 42})
        self.assertIsNot(value, got)
        self.assertEqual('abcd42ef0123456', got.digest)
