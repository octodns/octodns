#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.record.aaaa import AaaaRecord
from octodns.record.exception import ValidationError
from octodns.zone import Zone


class TestRecordAaaa(TestCase):
    zone = Zone('unit.tests.', [])

    def assertMultipleValues(self, _type, a_values, b_value):
        a_data = {'ttl': 30, 'values': a_values}
        a = _type(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values, a.values)
        self.assertEqual(a_data, a.data)

        b_data = {'ttl': 30, 'value': b_value}
        b = _type(self.zone, 'b', b_data)
        self.assertEqual([b_value], b.values)
        self.assertEqual(b_data, b.data)

    def test_aaaa(self):
        a_values = [
            '2001:db8:3c4d:15::1a2f:1a2b',
            '2001:db8:3c4d:15::1a2f:1a3b',
        ]
        b_value = '2001:db8:3c4d:15::1a2f:1a4b'
        self.assertMultipleValues(AaaaRecord, a_values, b_value)

        # Specifically validate that we normalize IPv6 addresses
        values = [
            '2001:db8:3c4d:15:0000:0000:1a2f:1a2b',
            '2001:0db8:3c4d:0015::1a2f:1a3b',
        ]
        data = {'ttl': 30, 'values': values}
        record = AaaaRecord(self.zone, 'aaaa', data)
        self.assertEqual(a_values, record.values)

    def test_validation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            '',
            {
                'type': 'AAAA',
                'ttl': 600,
                'value': '2601:644:500:e210:62f8:1dff:feb8:947a',
            },
        )
        Record.new(
            self.zone,
            '',
            {
                'type': 'AAAA',
                'ttl': 600,
                'values': ['2601:644:500:e210:62f8:1dff:feb8:947a'],
            },
        )
        Record.new(
            self.zone,
            '',
            {
                'type': 'AAAA',
                'ttl': 600,
                'values': [
                    '2601:644:500:e210:62f8:1dff:feb8:947a',
                    '2601:642:500:e210:62f8:1dff:feb8:947a',
                ],
            },
        )

        # missing value(s), no value or value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'AAAA', 'ttl': 600})
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing value(s), empty values
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, 'www', {'type': 'AAAA', 'ttl': 600, 'values': []}
            )
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing value(s), None values
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, 'www', {'type': 'AAAA', 'ttl': 600, 'values': None}
            )
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing value(s) and empty value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'www',
                {'type': 'AAAA', 'ttl': 600, 'values': [None, '']},
            )
        self.assertEqual(
            ['missing value(s)', 'empty value'], ctx.exception.reasons
        )

        # missing value(s), None value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, 'www', {'type': 'AAAA', 'ttl': 600, 'value': None}
            )
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # empty value, empty string value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, 'www', {'type': 'AAAA', 'ttl': 600, 'value': ''}
            )
        self.assertEqual(['empty value'], ctx.exception.reasons)

        # missing value(s) & ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'AAAA'})
        self.assertEqual(
            ['missing ttl', 'missing value(s)'], ctx.exception.reasons
        )

        # invalid IPv6 address
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, '', {'type': 'AAAA', 'ttl': 600, 'value': 'hello'}
            )
        self.assertEqual(
            ['invalid IPv6 address "hello"'], ctx.exception.reasons
        )

        # invalid IPv6 addresses
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {'type': 'AAAA', 'ttl': 600, 'values': ['hello', 'goodbye']},
            )
        self.assertEqual(
            ['invalid IPv6 address "hello"', 'invalid IPv6 address "goodbye"'],
            ctx.exception.reasons,
        )

        # invalid & valid IPv6 addresses, no ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'AAAA',
                    'values': [
                        '2601:644:500:e210:62f8:1dff:feb8:947a',
                        'hello',
                        '2601:642:500:e210:62f8:1dff:feb8:947a',
                    ],
                },
            )
        self.assertEqual(
            ['missing ttl', 'invalid IPv6 address "hello"'],
            ctx.exception.reasons,
        )

    def test_more_validation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            '',
            {
                'type': 'AAAA',
                'ttl': 600,
                'value': '2601:644:500:e210:62f8:1dff:feb8:947a',
            },
        )
        Record.new(
            self.zone,
            '',
            {
                'type': 'AAAA',
                'ttl': 600,
                'values': [
                    '2601:644:500:e210:62f8:1dff:feb8:947a',
                    '2601:644:500:e210:62f8:1dff:feb8:947b',
                ],
            },
        )

        # invalid ip address
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, '', {'type': 'AAAA', 'ttl': 600, 'value': 'hello'}
            )
        self.assertEqual(
            ['invalid IPv6 address "hello"'], ctx.exception.reasons
        )
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {'type': 'AAAA', 'ttl': 600, 'values': ['1.2.3.4', '2.3.4.5']},
            )
        self.assertEqual(
            [
                'invalid IPv6 address "1.2.3.4"',
                'invalid IPv6 address "2.3.4.5"',
            ],
            ctx.exception.reasons,
        )

        # invalid ip addresses
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {'type': 'AAAA', 'ttl': 600, 'values': ['hello', 'goodbye']},
            )
        self.assertEqual(
            ['invalid IPv6 address "hello"', 'invalid IPv6 address "goodbye"'],
            ctx.exception.reasons,
        )
