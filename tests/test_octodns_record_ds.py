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
            # diff flags
            (
                {
                    'flags': 0,
                    'protocol': 1,
                    'algorithm': 2,
                    'public_key': 'abcdef0123456',
                },
                {
                    'flags': 1,
                    'protocol': 1,
                    'algorithm': 2,
                    'public_key': 'abcdef0123456',
                },
            ),
            # diff protocol
            (
                {
                    'flags': 0,
                    'protocol': 1,
                    'algorithm': 2,
                    'public_key': 'abcdef0123456',
                },
                {
                    'flags': 0,
                    'protocol': 2,
                    'algorithm': 2,
                    'public_key': 'abcdef0123456',
                },
            ),
            # diff algorithm
            (
                {
                    'flags': 0,
                    'protocol': 1,
                    'algorithm': 2,
                    'public_key': 'abcdef0123456',
                },
                {
                    'flags': 0,
                    'protocol': 1,
                    'algorithm': 3,
                    'public_key': 'abcdef0123456',
                },
            ),
            # diff public_key
            (
                {
                    'flags': 0,
                    'protocol': 1,
                    'algorithm': 2,
                    'public_key': 'abcdef0123456',
                },
                {
                    'flags': 0,
                    'protocol': 1,
                    'algorithm': 2,
                    'public_key': 'bcdef0123456a',
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
                'flags': 'one',
                'protocol': 'two',
                'algorithm': 'three',
                'public_key': 'key',
            },
            DsValue.parse_rdata_text('one two three key'),
        )

        # valid
        data = {
            'flags': 0,
            'protocol': 1,
            'algorithm': 2,
            'public_key': '99148c81',
        }
        self.assertEqual(data, DsValue.parse_rdata_text('0 1 2 99148c81'))
        self.assertEqual([], DsValue.validate(data, 'DS'))

        # missing flags
        data = {'protocol': 1, 'algorithm': 2, 'public_key': '99148c81'}
        self.assertEqual(['missing flags'], DsValue.validate(data, 'DS'))
        # invalid flags
        data = {
            'flags': 'a',
            'protocol': 1,
            'algorithm': 2,
            'public_key': '99148c81',
        }
        self.assertEqual(['invalid flags "a"'], DsValue.validate(data, 'DS'))

        # missing protocol
        data = {'flags': 1, 'algorithm': 2, 'public_key': '99148c81'}
        self.assertEqual(['missing protocol'], DsValue.validate(data, 'DS'))
        # invalid protocol
        data = {
            'flags': 1,
            'protocol': 'a',
            'algorithm': 2,
            'public_key': '99148c81',
        }
        self.assertEqual(['invalid protocol "a"'], DsValue.validate(data, 'DS'))

        # missing algorithm
        data = {'flags': 1, 'protocol': 2, 'public_key': '99148c81'}
        self.assertEqual(['missing algorithm'], DsValue.validate(data, 'DS'))
        # invalid algorithm
        data = {
            'flags': 1,
            'protocol': 2,
            'algorithm': 'a',
            'public_key': '99148c81',
        }
        self.assertEqual(
            ['invalid algorithm "a"'], DsValue.validate(data, 'DS')
        )

        # missing algorithm (list)
        data = {'flags': 1, 'protocol': 2, 'algorithm': 3}
        self.assertEqual(['missing public_key'], DsValue.validate([data], 'DS'))

        zone = Zone('unit.tests.', [])
        values = [
            {
                'flags': 0,
                'protocol': 1,
                'algorithm': 2,
                'public_key': '99148c81',
            },
            {
                'flags': 1,
                'protocol': 2,
                'algorithm': 3,
                'public_key': '99148c44',
            },
        ]
        a = DsRecord(zone, 'ds', {'ttl': 32, 'values': values})
        self.assertEqual(0, a.values[0].flags)
        a.values[0].flags += 1
        self.assertEqual(1, a.values[0].flags)

        self.assertEqual(1, a.values[0].protocol)
        a.values[0].protocol += 1
        self.assertEqual(2, a.values[0].protocol)

        self.assertEqual(2, a.values[0].algorithm)
        a.values[0].algorithm += 1
        self.assertEqual(3, a.values[0].algorithm)

        self.assertEqual('99148c81', a.values[0].public_key)
        a.values[0].public_key = '99148c42'
        self.assertEqual('99148c42', a.values[0].public_key)

        self.assertEqual(1, a.values[1].flags)
        self.assertEqual(2, a.values[1].protocol)
        self.assertEqual(3, a.values[1].algorithm)
        self.assertEqual('99148c44', a.values[1].public_key)

        self.assertEqual(DsValue(values[1]), a.values[1].data)
        self.assertEqual('1 2 3 99148c44', a.values[1].rdata_text)
        self.assertEqual('1 2 3 99148c44', a.values[1].__repr__())
