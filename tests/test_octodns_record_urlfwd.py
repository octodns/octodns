#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.rr import RrParseError
from octodns.record.urlfwd import UrlfwdRecord, UrlfwdValue
from octodns.zone import Zone


class TestRecordUrlfwd(TestCase):
    zone = Zone('unit.tests.', [])

    def test_urlfwd(self):
        a_values = [
            UrlfwdValue(
                {
                    'path': '/',
                    'target': 'http://foo',
                    'code': 301,
                    'masking': 2,
                    'query': 0,
                }
            ),
            UrlfwdValue(
                {
                    'path': '/target',
                    'target': 'http://target',
                    'code': 302,
                    'masking': 2,
                    'query': 0,
                }
            ),
        ]
        a_data = {'ttl': 30, 'values': a_values}
        a = UrlfwdRecord(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values[0]['path'], a.values[0].path)
        self.assertEqual(a_values[0]['target'], a.values[0].target)
        self.assertEqual(a_values[0]['code'], a.values[0].code)
        self.assertEqual(a_values[0]['masking'], a.values[0].masking)
        self.assertEqual(a_values[0]['query'], a.values[0].query)
        self.assertEqual(a_values[1]['path'], a.values[1].path)
        self.assertEqual(a_values[1]['target'], a.values[1].target)
        self.assertEqual(a_values[1]['code'], a.values[1].code)
        self.assertEqual(a_values[1]['masking'], a.values[1].masking)
        self.assertEqual(a_values[1]['query'], a.values[1].query)
        self.assertEqual(a_data, a.data)

        b_value = UrlfwdValue(
            {
                'path': '/',
                'target': 'http://location',
                'code': 301,
                'masking': 2,
                'query': 0,
            }
        )
        b_data = {'ttl': 30, 'value': b_value}
        b = UrlfwdRecord(self.zone, 'b', b_data)
        self.assertEqual(b_value['path'], b.values[0].path)
        self.assertEqual(b_value['target'], b.values[0].target)
        self.assertEqual(b_value['code'], b.values[0].code)
        self.assertEqual(b_value['masking'], b.values[0].masking)
        self.assertEqual(b_value['query'], b.values[0].query)
        self.assertEqual(b_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in path causes change
        other = UrlfwdRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].path = '/change'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in target causes change
        other = UrlfwdRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].target = 'http://target'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in code causes change
        other = UrlfwdRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].code = 302
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in masking causes change
        other = UrlfwdRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].masking = 0
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in query causes change
        other = UrlfwdRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].query = 1
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # hash
        v = UrlfwdValue(
            {
                'path': '/',
                'target': 'http://place',
                'code': 301,
                'masking': 2,
                'query': 0,
            }
        )
        o = UrlfwdValue(
            {
                'path': '/location',
                'target': 'http://redirect',
                'code': 302,
                'masking': 2,
                'query': 0,
            }
        )
        values = set()
        values.add(v)
        self.assertTrue(v in values)
        self.assertFalse(o in values)
        values.add(o)
        self.assertTrue(o in values)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_validation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            '',
            {
                'type': 'URLFWD',
                'ttl': 600,
                'value': {
                    'path': '/',
                    'target': 'http://foo',
                    'code': 301,
                    'masking': 2,
                    'query': 0,
                },
            },
        )
        Record.new(
            self.zone,
            '',
            {
                'type': 'URLFWD',
                'ttl': 600,
                'values': [
                    {
                        'path': '/',
                        'target': 'http://foo',
                        'code': 301,
                        'masking': 2,
                        'query': 0,
                    },
                    {
                        'path': '/target',
                        'target': 'http://target',
                        'code': 302,
                        'masking': 2,
                        'query': 0,
                    },
                ],
            },
        )

        # missing path
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'URLFWD',
                    'ttl': 600,
                    'value': {
                        'target': 'http://foo',
                        'code': 301,
                        'masking': 2,
                        'query': 0,
                    },
                },
            )
        self.assertEqual(['missing path'], ctx.exception.reasons)

        # missing target
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'URLFWD',
                    'ttl': 600,
                    'value': {
                        'path': '/',
                        'code': 301,
                        'masking': 2,
                        'query': 0,
                    },
                },
            )
        self.assertEqual(['missing target'], ctx.exception.reasons)

        # missing code
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'URLFWD',
                    'ttl': 600,
                    'value': {
                        'path': '/',
                        'target': 'http://foo',
                        'masking': 2,
                        'query': 0,
                    },
                },
            )
        self.assertEqual(['missing code'], ctx.exception.reasons)

        # invalid code
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'URLFWD',
                    'ttl': 600,
                    'value': {
                        'path': '/',
                        'target': 'http://foo',
                        'code': 'nope',
                        'masking': 2,
                        'query': 0,
                    },
                },
            )
        self.assertEqual(['invalid return code "nope"'], ctx.exception.reasons)

        # unrecognized code
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'URLFWD',
                    'ttl': 600,
                    'value': {
                        'path': '/',
                        'target': 'http://foo',
                        'code': 3,
                        'masking': 2,
                        'query': 0,
                    },
                },
            )
        self.assertEqual(
            ['unrecognized return code "3"'], ctx.exception.reasons
        )

        # missing masking
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'URLFWD',
                    'ttl': 600,
                    'value': {
                        'path': '/',
                        'target': 'http://foo',
                        'code': 301,
                        'query': 0,
                    },
                },
            )
        self.assertEqual(['missing masking'], ctx.exception.reasons)

        # invalid masking
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'URLFWD',
                    'ttl': 600,
                    'value': {
                        'path': '/',
                        'target': 'http://foo',
                        'code': 301,
                        'masking': 'nope',
                        'query': 0,
                    },
                },
            )
        self.assertEqual(
            ['invalid masking setting "nope"'], ctx.exception.reasons
        )

        # unrecognized masking
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'URLFWD',
                    'ttl': 600,
                    'value': {
                        'path': '/',
                        'target': 'http://foo',
                        'code': 301,
                        'masking': 3,
                        'query': 0,
                    },
                },
            )
        self.assertEqual(
            ['unrecognized masking setting "3"'], ctx.exception.reasons
        )

        # missing query
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'URLFWD',
                    'ttl': 600,
                    'value': {
                        'path': '/',
                        'target': 'http://foo',
                        'code': 301,
                        'masking': 2,
                    },
                },
            )
        self.assertEqual(['missing query'], ctx.exception.reasons)

        # invalid query
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'URLFWD',
                    'ttl': 600,
                    'value': {
                        'path': '/',
                        'target': 'http://foo',
                        'code': 301,
                        'masking': 2,
                        'query': 'nope',
                    },
                },
            )
        self.assertEqual(
            ['invalid query setting "nope"'], ctx.exception.reasons
        )

        # unrecognized query
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'URLFWD',
                    'ttl': 600,
                    'value': {
                        'path': '/',
                        'target': 'http://foo',
                        'code': 301,
                        'masking': 2,
                        'query': 3,
                    },
                },
            )
        self.assertEqual(
            ['unrecognized query setting "3"'], ctx.exception.reasons
        )

    def test_urlfwd_value_rdata_text(self):
        # empty string won't parse
        with self.assertRaises(RrParseError):
            UrlfwdValue.parse_rdata_text('')

        # single word won't parse
        with self.assertRaises(RrParseError):
            UrlfwdValue.parse_rdata_text('nope')

        # 2nd word won't parse
        with self.assertRaises(RrParseError):
            UrlfwdValue.parse_rdata_text('1 2')

        # 3rd word won't parse
        with self.assertRaises(RrParseError):
            UrlfwdValue.parse_rdata_text('1 2 3')

        # 4th word won't parse
        with self.assertRaises(RrParseError):
            UrlfwdValue.parse_rdata_text('1 2 3 4')

        # 6th word won't parse
        with self.assertRaises(RrParseError):
            UrlfwdValue.parse_rdata_text('1 2 3 4 5 6')

        # code, masking, and query not ints
        self.assertEqual(
            {
                'path': 'one',
                'target': 'urlfwd.unit.tests.',
                'code': 'one',
                'masking': 'two',
                'query': 'three',
            },
            UrlfwdValue.parse_rdata_text(
                'one urlfwd.unit.tests. one two three'
            ),
        )

        # valid
        self.assertEqual(
            {
                'path': 'one',
                'target': 'urlfwd.unit.tests.',
                'code': 1,
                'masking': 2,
                'query': 3,
            },
            UrlfwdValue.parse_rdata_text('one urlfwd.unit.tests. 1 2 3'),
        )

        # quoted
        self.assertEqual(
            {
                'path': 'one',
                'target': 'urlfwd.unit.tests.',
                'code': 1,
                'masking': 2,
                'query': 3,
            },
            UrlfwdValue.parse_rdata_text('"one" "urlfwd.unit.tests." 1 2 3'),
        )

        zone = Zone('unit.tests.', [])
        a = UrlfwdRecord(
            zone,
            'urlfwd',
            {
                'ttl': 32,
                'value': {
                    'path': 'one',
                    'target': 'urlfwd.unit.tests.',
                    'code': 1,
                    'masking': 2,
                    'query': 3,
                },
            },
        )
        self.assertEqual('one', a.values[0].path)
        self.assertEqual('urlfwd.unit.tests.', a.values[0].target)
        self.assertEqual(1, a.values[0].code)
        self.assertEqual(2, a.values[0].masking)
        self.assertEqual(3, a.values[0].query)

        # both directions should match
        rdata = '"one" "urlfwd.unit.tests." 1 2 3'
        record = UrlfwdRecord(
            zone,
            'urlfwd',
            {'ttl': 32, 'value': UrlfwdValue.parse_rdata_text(rdata)},
        )
        self.assertEqual(rdata, record.values[0].rdata_text)
