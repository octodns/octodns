#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.exception import ValidationError
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
