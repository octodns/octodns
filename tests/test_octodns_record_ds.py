#
#
#

from unittest import TestCase

from octodns.record.ds import DsRecord, DsValue
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
        self.assertEqual([], DsValue.validate(data, 'DS'))

        # missing key_tag
        data = {'algorithm': 1, 'digest_type': 2, 'digest': '99148c81'}
        self.assertEqual(['missing key_tag'], DsValue.validate(data, 'DS'))
        # invalid key_tag
        data = {
            'key_tag': 'a',
            'algorithm': 1,
            'digest_type': 2,
            'digest': '99148c81',
        }
        self.assertEqual(['invalid key_tag "a"'], DsValue.validate(data, 'DS'))

        # missing algorithm
        data = {'key_tag': 1, 'digest_type': 2, 'digest': '99148c81'}
        self.assertEqual(['missing algorithm'], DsValue.validate(data, 'DS'))
        # invalid algorithm
        data = {
            'key_tag': 1,
            'algorithm': 'a',
            'digest_type': 2,
            'digest': '99148c81',
        }
        self.assertEqual(
            ['invalid algorithm "a"'], DsValue.validate(data, 'DS')
        )

        # missing digest_type
        data = {'key_tag': 1, 'algorithm': 2, 'digest': '99148c81'}
        self.assertEqual(['missing digest_type'], DsValue.validate(data, 'DS'))
        # invalid digest_type
        data = {
            'key_tag': 1,
            'algorithm': 2,
            'digest_type': 'a',
            'digest': '99148c81',
        }
        self.assertEqual(
            ['invalid digest_type "a"'], DsValue.validate(data, 'DS')
        )

        # missing public_key (list)
        data = {'key_tag': 1, 'algorithm': 2, 'digest_type': 3}
        self.assertEqual(['missing digest'], DsValue.validate([data], 'DS'))

        # do validations again with old field style

        # missing flags (list)
        data = {'protocol': 2, 'algorithm': 3, 'public_key': '99148c81'}
        self.assertEqual(['missing flags'], DsValue.validate([data], 'DS'))

        # missing protocol (list)
        data = {'flags': 1, 'algorithm': 3, 'public_key': '99148c81'}
        self.assertEqual(['missing protocol'], DsValue.validate([data], 'DS'))

        # missing algorithm (list)
        data = {'flags': 1, 'protocol': 2, 'public_key': '99148c81'}
        self.assertEqual(['missing algorithm'], DsValue.validate([data], 'DS'))

        # missing public_key (list)
        data = {'flags': 1, 'algorithm': 3, 'protocol': 2}
        self.assertEqual(['missing public_key'], DsValue.validate([data], 'DS'))

        # missing public_key (list)
        data = {'flags': 1, 'algorithm': 3, 'protocol': 2, 'digest': '99148c81'}
        self.assertEqual(['missing public_key'], DsValue.validate([data], 'DS'))

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
            DsValue.validate(data, 'DS'),
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
