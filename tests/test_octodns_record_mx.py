#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.mx import MxRecord, MxValue
from octodns.record.rr import RrParseError
from octodns.zone import Zone


class TestRecordMx(TestCase):
    zone = Zone('unit.tests.', [])

    def test_mx(self):
        a_values = [
            MxValue({'preference': 10, 'exchange': 'smtp1.'}),
            MxValue({'priority': 20, 'value': 'smtp2.'}),
        ]
        a_data = {'ttl': 30, 'values': a_values}
        a = MxRecord(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values[0]['preference'], a.values[0].preference)
        self.assertEqual(a_values[0]['exchange'], a.values[0].exchange)
        self.assertEqual(a_values[1]['preference'], a.values[1].preference)
        self.assertEqual(a_values[1]['exchange'], a.values[1].exchange)
        a_data['values'][1] = MxValue({'preference': 20, 'exchange': 'smtp2.'})
        self.assertEqual(a_data, a.data)

        b_value = MxValue({'preference': 0, 'exchange': 'smtp3.'})
        b_data = {'ttl': 30, 'value': b_value}
        b = MxRecord(self.zone, 'b', b_data)
        self.assertEqual(b_value['preference'], b.values[0].preference)
        self.assertEqual(b_value['exchange'], b.values[0].exchange)
        self.assertEqual(b_data, b.data)

        a_upper_values = [
            {'preference': 10, 'exchange': 'SMTP1.'},
            {'priority': 20, 'value': 'SMTP2.'},
        ]
        a_upper_data = {'ttl': 30, 'values': a_upper_values}
        a_upper = MxRecord(self.zone, 'a', a_upper_data)
        self.assertEqual(a_upper.data, a.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in preference causes change
        other = MxRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].preference = 22
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in value causes change
        other.values[0].preference = a.values[0].preference
        other.values[0].exchange = 'smtpX'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_mx_value_rdata_text(self):
        # empty string won't parse
        with self.assertRaises(RrParseError):
            MxValue.parse_rdata_text('')

        # single word won't parse
        with self.assertRaises(RrParseError):
            MxValue.parse_rdata_text('nope')

        # 3rd word won't parse
        with self.assertRaises(RrParseError):
            MxValue.parse_rdata_text('10 mx.unit.tests. another')

        # preference not an int
        self.assertEqual(
            {'preference': 'abc', 'exchange': 'mx.unit.tests.'},
            MxValue.parse_rdata_text('abc mx.unit.tests.'),
        )

        # valid
        self.assertEqual(
            {'preference': 10, 'exchange': 'mx.unit.tests.'},
            MxValue.parse_rdata_text('10 mx.unit.tests.'),
        )

        # quoted
        self.assertEqual(
            {'preference': 10, 'exchange': 'mx.unit.tests.'},
            MxValue.parse_rdata_text('10 "mx.unit.tests."'),
        )

        zone = Zone('unit.tests.', [])
        a = MxRecord(
            zone,
            'mx',
            {
                'ttl': 32,
                'values': [
                    {'preference': 11, 'exchange': 'mail1.unit.tests.'},
                    {'preference': 12, 'exchange': 'mail2.unit.tests.'},
                ],
            },
        )
        self.assertEqual(11, a.values[0].preference)
        self.assertEqual('mail1.unit.tests.', a.values[0].exchange)
        self.assertEqual('11 mail1.unit.tests.', a.values[0].rdata_text)
        self.assertEqual(12, a.values[1].preference)
        self.assertEqual('mail2.unit.tests.', a.values[1].exchange)
        self.assertEqual('12 mail2.unit.tests.', a.values[1].rdata_text)

    def test_mx_value(self):
        a = MxValue(
            {'preference': 0, 'priority': 'a', 'exchange': 'v', 'value': '1'}
        )
        b = MxValue(
            {'preference': 10, 'priority': 'a', 'exchange': 'v', 'value': '2'}
        )
        c = MxValue(
            {'preference': 0, 'priority': 'b', 'exchange': 'z', 'value': '3'}
        )

        self.assertEqual(a, a)
        self.assertEqual(b, b)
        self.assertEqual(c, c)

        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(b, a)
        self.assertNotEqual(b, c)
        self.assertNotEqual(c, a)
        self.assertNotEqual(c, b)

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

        self.assertEqual(a.__hash__(), a.__hash__())
        self.assertNotEqual(a.__hash__(), b.__hash__())

    def test_validation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            '',
            {
                'type': 'MX',
                'ttl': 600,
                'value': {'preference': 10, 'exchange': 'foo.bar.com.'},
            },
        )

        # missing preference
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'MX',
                    'ttl': 600,
                    'value': {'exchange': 'foo.bar.com.'},
                },
            )
        self.assertEqual(['missing preference'], ctx.exception.reasons)

        # invalid preference
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'MX',
                    'ttl': 600,
                    'value': {'preference': 'nope', 'exchange': 'foo.bar.com.'},
                },
            )
        self.assertEqual(['invalid preference "nope"'], ctx.exception.reasons)

        # missing exchange
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {'type': 'MX', 'ttl': 600, 'value': {'preference': 10}},
            )
        self.assertEqual(['missing exchange'], ctx.exception.reasons)

        # missing trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'MX',
                    'ttl': 600,
                    'value': {'preference': 10, 'exchange': 'foo.bar.com'},
                },
            )
        self.assertEqual(
            ['MX value "foo.bar.com" missing trailing .'], ctx.exception.reasons
        )

        # exchange must be a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'MX',
                    'ttl': 600,
                    'value': {'preference': 10, 'exchange': '100 foo.bar.com.'},
                },
            )
        self.assertEqual(
            ['Invalid MX exchange "100 foo.bar.com." is not a valid FQDN.'],
            ctx.exception.reasons,
        )

        # if exchange doesn't exist value can not be None/falsey
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'MX',
                    'ttl': 600,
                    'value': {'preference': 10, 'value': ''},
                },
            )
        self.assertEqual(['missing exchange'], ctx.exception.reasons)

        # exchange can be a single `.`
        record = Record.new(
            self.zone,
            '',
            {
                'type': 'MX',
                'ttl': 600,
                'value': {'preference': 0, 'exchange': '.'},
            },
        )
        self.assertEqual('.', record.values[0].exchange)
