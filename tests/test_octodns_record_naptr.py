#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.naptr import NaptrRecord, NaptrValue
from octodns.record.rr import RrParseError
from octodns.zone import Zone


class TestRecordNaptr(TestCase):
    zone = Zone('unit.tests.', [])

    def test_naptr(self):
        a_values = [
            NaptrValue(
                {
                    'order': 10,
                    'preference': 11,
                    'flags': 'X',
                    'service': 'Y',
                    'regexp': 'Z',
                    'replacement': '.',
                }
            ),
            NaptrValue(
                {
                    'order': 20,
                    'preference': 21,
                    'flags': 'A',
                    'service': 'B',
                    'regexp': 'C',
                    'replacement': 'foo.com',
                }
            ),
        ]
        a_data = {'ttl': 30, 'values': a_values}
        a = NaptrRecord(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        for i in (0, 1):
            for k in a_values[0].keys():
                self.assertEqual(a_values[i][k], getattr(a.values[i], k))
        self.assertEqual(a_data, a.data)

        b_value = NaptrValue(
            {
                'order': 30,
                'preference': 31,
                'flags': 'M',
                'service': 'N',
                'regexp': 'O',
                'replacement': 'x',
            }
        )
        b_data = {'ttl': 30, 'value': b_value}
        b = NaptrRecord(self.zone, 'b', b_data)
        for k in a_values[0].keys():
            self.assertEqual(b_value[k], getattr(b.values[0], k))
        self.assertEqual(b_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in priority causes change
        other = NaptrRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].order = 22
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in replacement causes change
        other.values[0].order = a.values[0].order
        other.values[0].replacement = 'smtpX'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # full sorting
        # equivalent
        b_naptr_value = b.values[0]
        self.assertTrue(b_naptr_value == b_naptr_value)
        self.assertFalse(b_naptr_value != b_naptr_value)
        self.assertTrue(b_naptr_value <= b_naptr_value)
        self.assertTrue(b_naptr_value >= b_naptr_value)
        # by order
        self.assertTrue(
            b_naptr_value
            > NaptrValue(
                {
                    'order': 10,
                    'preference': 31,
                    'flags': 'M',
                    'service': 'N',
                    'regexp': 'O',
                    'replacement': 'x',
                }
            )
        )
        self.assertTrue(
            b_naptr_value
            < NaptrValue(
                {
                    'order': 40,
                    'preference': 31,
                    'flags': 'M',
                    'service': 'N',
                    'regexp': 'O',
                    'replacement': 'x',
                }
            )
        )
        # by preference
        self.assertTrue(
            b_naptr_value
            > NaptrValue(
                {
                    'order': 30,
                    'preference': 10,
                    'flags': 'M',
                    'service': 'N',
                    'regexp': 'O',
                    'replacement': 'x',
                }
            )
        )
        self.assertTrue(
            b_naptr_value
            < NaptrValue(
                {
                    'order': 30,
                    'preference': 40,
                    'flags': 'M',
                    'service': 'N',
                    'regexp': 'O',
                    'replacement': 'x',
                }
            )
        )
        # by flags
        self.assertTrue(
            b_naptr_value
            > NaptrValue(
                {
                    'order': 30,
                    'preference': 31,
                    'flags': 'A',
                    'service': 'N',
                    'regexp': 'O',
                    'replacement': 'x',
                }
            )
        )
        self.assertTrue(
            b_naptr_value
            < NaptrValue(
                {
                    'order': 30,
                    'preference': 31,
                    'flags': 'Z',
                    'service': 'N',
                    'regexp': 'O',
                    'replacement': 'x',
                }
            )
        )
        # by service
        self.assertTrue(
            b_naptr_value
            > NaptrValue(
                {
                    'order': 30,
                    'preference': 31,
                    'flags': 'M',
                    'service': 'A',
                    'regexp': 'O',
                    'replacement': 'x',
                }
            )
        )
        self.assertTrue(
            b_naptr_value
            < NaptrValue(
                {
                    'order': 30,
                    'preference': 31,
                    'flags': 'M',
                    'service': 'Z',
                    'regexp': 'O',
                    'replacement': 'x',
                }
            )
        )
        # by regexp
        self.assertTrue(
            b_naptr_value
            > NaptrValue(
                {
                    'order': 30,
                    'preference': 31,
                    'flags': 'M',
                    'service': 'N',
                    'regexp': 'A',
                    'replacement': 'x',
                }
            )
        )
        self.assertTrue(
            b_naptr_value
            < NaptrValue(
                {
                    'order': 30,
                    'preference': 31,
                    'flags': 'M',
                    'service': 'N',
                    'regexp': 'Z',
                    'replacement': 'x',
                }
            )
        )
        # by replacement
        self.assertTrue(
            b_naptr_value
            > NaptrValue(
                {
                    'order': 30,
                    'preference': 31,
                    'flags': 'M',
                    'service': 'N',
                    'regexp': 'O',
                    'replacement': 'a',
                }
            )
        )
        self.assertTrue(
            b_naptr_value
            < NaptrValue(
                {
                    'order': 30,
                    'preference': 31,
                    'flags': 'M',
                    'service': 'N',
                    'regexp': 'O',
                    'replacement': 'z',
                }
            )
        )

        # __repr__ doesn't blow up
        a.__repr__()

        # Hash
        v = NaptrValue(
            {
                'order': 30,
                'preference': 31,
                'flags': 'M',
                'service': 'N',
                'regexp': 'O',
                'replacement': 'z',
            }
        )
        o = NaptrValue(
            {
                'order': 30,
                'preference': 32,
                'flags': 'M',
                'service': 'N',
                'regexp': 'O',
                'replacement': 'z',
            }
        )
        values = set()
        values.add(v)
        self.assertTrue(v in values)
        self.assertFalse(o in values)
        values.add(o)
        self.assertTrue(o in values)

        self.assertEqual(30, o.order)
        o.order = o.order + 1
        self.assertEqual(31, o.order)

        self.assertEqual(32, o.preference)
        o.preference = o.preference + 1
        self.assertEqual(33, o.preference)

        self.assertEqual('M', o.flags)
        o.flags = 'P'
        self.assertEqual('P', o.flags)

        self.assertEqual('N', o.service)
        o.service = 'Q'
        self.assertEqual('Q', o.service)

        self.assertEqual('O', o.regexp)
        o.regexp = 'R'
        self.assertEqual('R', o.regexp)

        self.assertEqual('z', o.replacement)
        o.replacement = '1'
        self.assertEqual('1', o.replacement)

    def test_naptr_value_rdata_text(self):
        # things with the wrong number of words won't parse
        for v in (
            '',
            'one',
            'one two',
            'one two three',
            'one two three four',
            'one two three four five',
            'one two three four five six seven',
        ):
            with self.assertRaises(RrParseError):
                NaptrValue.parse_rdata_text(v)

        # we don't care if the types of things are correct when parsing rr text
        self.assertEqual(
            {
                'order': 'one',
                'preference': 'two',
                'flags': 'three',
                'service': 'four',
                'regexp': 'five',
                'replacement': 'six',
            },
            NaptrValue.parse_rdata_text('one two three four five six'),
        )

        # order and preference will be converted to int's when possible
        self.assertEqual(
            {
                'order': 1,
                'preference': 2,
                'flags': 'three',
                'service': 'four',
                'regexp': 'five',
                'replacement': 'six',
            },
            NaptrValue.parse_rdata_text('1 2 three four five six'),
        )

        # string fields are unquoted if needed
        self.assertEqual(
            {
                'order': 1,
                'preference': 2,
                'flags': 'three',
                'service': 'four',
                'regexp': 'five',
                'replacement': 'six',
            },
            NaptrValue.parse_rdata_text('1 2 "three" "four" "five" "six"'),
        )

        # make sure that the cstor is using parse_rdata_text
        zone = Zone('unit.tests.', [])
        a = NaptrRecord(
            zone,
            'naptr',
            {
                'ttl': 32,
                'value': {
                    'order': 1,
                    'preference': 2,
                    'flags': 'S',
                    'service': 'service',
                    'regexp': 'regexp',
                    'replacement': 'replacement',
                },
            },
        )
        self.assertEqual(1, a.values[0].order)
        self.assertEqual(2, a.values[0].preference)
        self.assertEqual('S', a.values[0].flags)
        self.assertEqual('service', a.values[0].service)
        self.assertEqual('regexp', a.values[0].regexp)
        self.assertEqual('replacement', a.values[0].replacement)
        s = '1 2 S service regexp replacement'
        self.assertEqual(s, a.values[0].rdata_text)

    def test_validation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            '',
            {
                'type': 'NAPTR',
                'ttl': 600,
                'value': {
                    'order': 10,
                    'preference': 20,
                    'flags': 'S',
                    'service': 'srv',
                    'regexp': '.*',
                    'replacement': '.',
                },
            },
        )

        # missing X priority
        value = {
            'order': 10,
            'preference': 20,
            'flags': 'S',
            'service': 'srv',
            'regexp': '.*',
            'replacement': '.',
        }
        for k in (
            'order',
            'preference',
            'flags',
            'service',
            'regexp',
            'replacement',
        ):
            v = dict(value)
            del v[k]
            with self.assertRaises(ValidationError) as ctx:
                Record.new(
                    self.zone, '', {'type': 'NAPTR', 'ttl': 600, 'value': v}
                )
            self.assertEqual([f'missing {k}'], ctx.exception.reasons)

        # non-int order
        v = dict(value)
        v['order'] = 'boo'
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'NAPTR', 'ttl': 600, 'value': v})
        self.assertEqual(['invalid order "boo"'], ctx.exception.reasons)

        # non-int preference
        v = dict(value)
        v['preference'] = 'who'
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'NAPTR', 'ttl': 600, 'value': v})
        self.assertEqual(['invalid preference "who"'], ctx.exception.reasons)

        # unrecognized flags
        v = dict(value)
        v['flags'] = 'X'
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'NAPTR', 'ttl': 600, 'value': v})
        self.assertEqual(['unrecognized flags "X"'], ctx.exception.reasons)
