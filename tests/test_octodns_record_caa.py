#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.caa import CaaRecord, CaaValue
from octodns.record.exception import ValidationError
from octodns.record.rr import RrParseError
from octodns.zone import Zone


class TestRecordCaa(TestCase):
    zone = Zone('unit.tests.', [])

    def test_caa(self):
        a_values = [
            CaaValue({'flags': 0, 'tag': 'issue', 'value': 'ca.example.net'}),
            CaaValue(
                {
                    'flags': 128,
                    'tag': 'iodef',
                    'value': 'mailto:security@example.com',
                }
            ),
        ]
        a_data = {'ttl': 30, 'values': a_values}
        a = CaaRecord(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values[0]['flags'], a.values[0].flags)
        self.assertEqual(a_values[0]['tag'], a.values[0].tag)
        self.assertEqual(a_values[0]['value'], a.values[0].value)
        self.assertEqual(a_values[1]['flags'], a.values[1].flags)
        self.assertEqual(a_values[1]['tag'], a.values[1].tag)
        self.assertEqual(a_values[1]['value'], a.values[1].value)
        self.assertEqual(a_data, a.data)

        b_value = CaaValue(
            {'tag': 'iodef', 'value': 'http://iodef.example.com/'}
        )
        b_data = {'ttl': 30, 'value': b_value}
        b = CaaRecord(self.zone, 'b', b_data)
        self.assertEqual(0, b.values[0].flags)
        self.assertEqual(b_value['tag'], b.values[0].tag)
        self.assertEqual(b_value['value'], b.values[0].value)
        b_data['value']['flags'] = 0
        self.assertEqual(b_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in flags causes change
        other = CaaRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].flags = 128
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in tag causes change
        other.values[0].flags = a.values[0].flags
        other.values[0].tag = 'foo'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in value causes change
        other.values[0].tag = a.values[0].tag
        other.values[0].value = 'bar'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_caa_value_rdata_text(self):
        # empty string won't parse
        with self.assertRaises(RrParseError):
            CaaValue.parse_rdata_text('')

        # single word won't parse
        with self.assertRaises(RrParseError):
            CaaValue.parse_rdata_text('nope')

        # 2nd word won't parse
        with self.assertRaises(RrParseError):
            CaaValue.parse_rdata_text('0 tag')

        # 4th word won't parse
        with self.assertRaises(RrParseError):
            CaaValue.parse_rdata_text('1 tag value another')

        # flags not an int, will parse
        self.assertEqual(
            {'flags': 'one', 'tag': 'tag', 'value': 'value'},
            CaaValue.parse_rdata_text('one tag value'),
        )

        # valid
        self.assertEqual(
            {'flags': 0, 'tag': 'tag', 'value': '99148c81'},
            CaaValue.parse_rdata_text('0 tag 99148c81'),
        )

        # quoted
        self.assertEqual(
            {'flags': 0, 'tag': 'tag', 'value': '99148c81'},
            CaaValue.parse_rdata_text('0 "tag" "99148c81"'),
        )

        zone = Zone('unit.tests.', [])
        a = CaaRecord(
            zone,
            'caa',
            {
                'ttl': 32,
                'values': [
                    {'flags': 1, 'tag': 'tag1', 'value': '99148c81'},
                    {'flags': 2, 'tag': 'tag2', 'value': '99148c44'},
                ],
            },
        )
        self.assertEqual(1, a.values[0].flags)
        self.assertEqual('tag1', a.values[0].tag)
        self.assertEqual('99148c81', a.values[0].value)
        self.assertEqual('1 tag1 99148c81', a.values[0].rdata_text)
        self.assertEqual(2, a.values[1].flags)
        self.assertEqual('tag2', a.values[1].tag)
        self.assertEqual('99148c44', a.values[1].value)
        self.assertEqual('2 tag2 99148c44', a.values[1].rdata_text)

    def test_caa_value(self):
        a = CaaValue({'flags': 0, 'tag': 'a', 'value': 'v'})
        b = CaaValue({'flags': 1, 'tag': 'a', 'value': 'v'})
        c = CaaValue({'flags': 0, 'tag': 'c', 'value': 'v'})
        d = CaaValue({'flags': 0, 'tag': 'a', 'value': 'z'})

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

        self.assertTrue(a < b)
        self.assertTrue(a < c)
        self.assertTrue(a < d)

        self.assertTrue(b > a)
        self.assertTrue(b > c)
        self.assertTrue(b > d)

        self.assertTrue(c > a)
        self.assertTrue(c < b)
        self.assertTrue(c > d)

        self.assertTrue(d > a)
        self.assertTrue(d < b)
        self.assertTrue(d < c)

        self.assertTrue(a <= b)
        self.assertTrue(a <= c)
        self.assertTrue(a <= d)
        self.assertTrue(a <= a)
        self.assertTrue(a >= a)

        self.assertTrue(b >= a)
        self.assertTrue(b >= c)
        self.assertTrue(b >= d)
        self.assertTrue(b >= b)
        self.assertTrue(b <= b)

        self.assertTrue(c >= a)
        self.assertTrue(c <= b)
        self.assertTrue(c >= d)
        self.assertTrue(c >= c)
        self.assertTrue(c <= c)

        self.assertTrue(d >= a)
        self.assertTrue(d <= b)
        self.assertTrue(d <= c)
        self.assertTrue(d >= d)
        self.assertTrue(d <= d)

    def test_validation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            '',
            {
                'type': 'CAA',
                'ttl': 600,
                'value': {
                    'flags': 128,
                    'tag': 'iodef',
                    'value': 'http://foo.bar.com/',
                },
            },
        )

        # invalid flags
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'CAA',
                    'ttl': 600,
                    'value': {
                        'flags': -42,
                        'tag': 'iodef',
                        'value': 'http://foo.bar.com/',
                    },
                },
            )
        self.assertEqual(['invalid flags "-42"'], ctx.exception.reasons)
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'CAA',
                    'ttl': 600,
                    'value': {
                        'flags': 442,
                        'tag': 'iodef',
                        'value': 'http://foo.bar.com/',
                    },
                },
            )
        self.assertEqual(['invalid flags "442"'], ctx.exception.reasons)
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'CAA',
                    'ttl': 600,
                    'value': {
                        'flags': 'nope',
                        'tag': 'iodef',
                        'value': 'http://foo.bar.com/',
                    },
                },
            )
        self.assertEqual(['invalid flags "nope"'], ctx.exception.reasons)

        # missing tag
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'CAA',
                    'ttl': 600,
                    'value': {'value': 'http://foo.bar.com/'},
                },
            )
        self.assertEqual(['missing tag'], ctx.exception.reasons)

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {'type': 'CAA', 'ttl': 600, 'value': {'tag': 'iodef'}},
            )
        self.assertEqual(['missing value'], ctx.exception.reasons)
