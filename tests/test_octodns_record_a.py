#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.a import ARecord
from octodns.record.exception import ValidationError
from octodns.zone import Zone


class TestRecordA(TestCase):
    zone = Zone('unit.tests.', [])

    def test_a_and_record(self):
        a_values = ['1.2.3.4', '2.2.3.4']
        a_data = {'ttl': 30, 'values': a_values}
        a = ARecord(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values, a.values)
        self.assertEqual(a_data, a.data)

        b_value = '3.2.3.4'
        b_data = {'ttl': 30, 'value': b_value}
        b = ARecord(self.zone, 'b', b_data)
        self.assertEqual([b_value], b.values)
        self.assertEqual(b_data, b.data)

        # top-level
        data = {'ttl': 30, 'value': '4.2.3.4'}
        self.assertEqual(self.zone.name, ARecord(self.zone, '', data).fqdn)
        self.assertEqual(self.zone.name, ARecord(self.zone, None, data).fqdn)

        # ARecord equate with itself
        self.assertTrue(a == a)
        # Records with differing names and same type don't equate
        self.assertFalse(a == b)
        # Records with same name & type equate even if ttl is different
        self.assertTrue(
            a == ARecord(self.zone, 'a', {'ttl': 31, 'values': a_values})
        )
        # Records with same name & type equate even if values are different
        self.assertTrue(
            a == ARecord(self.zone, 'a', {'ttl': 30, 'value': b_value})
        )

        target = SimpleProvider()
        # no changes if self
        self.assertFalse(a.changes(a, target))
        # no changes if clone
        other = ARecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        self.assertFalse(a.changes(other, target))
        # changes if ttl modified
        other.ttl = 31
        update = a.changes(other, target)
        self.assertEqual(a, update.existing)
        self.assertEqual(other, update.new)
        # changes if values modified
        other.ttl = a.ttl
        other.values = ['4.4.4.4']
        update = a.changes(other, target)
        self.assertEqual(a, update.existing)
        self.assertEqual(other, update.new)

        # Hashing
        records = set()
        records.add(a)
        self.assertTrue(a in records)
        self.assertFalse(b in records)
        records.add(b)
        self.assertTrue(b in records)

        # __repr__ doesn't blow up
        a.__repr__()
        # Record.__repr__ does
        with self.assertRaises(NotImplementedError):

            class DummyRecord(Record):
                def __init__(self):
                    pass

            DummyRecord().__repr__()

    def test_validation_and_values_mixin(self):
        # doesn't blow up
        Record.new(self.zone, '', {'type': 'A', 'ttl': 600, 'value': '1.2.3.4'})
        Record.new(
            self.zone, '', {'type': 'A', 'ttl': 600, 'values': ['1.2.3.4']}
        )
        Record.new(
            self.zone,
            '',
            {'type': 'A', 'ttl': 600, 'values': ['1.2.3.4', '1.2.3.5']},
        )

        # missing value(s), no value or value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'A', 'ttl': 600})
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing value(s), empty values
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, 'www', {'type': 'A', 'ttl': 600, 'values': []}
            )
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing value(s), None values
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, 'www', {'type': 'A', 'ttl': 600, 'values': None}
            )
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing value(s) and empty value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'www',
                {'type': 'A', 'ttl': 600, 'values': [None, '']},
            )
        self.assertEqual(
            ['missing value(s)', 'empty value'], ctx.exception.reasons
        )

        # missing value(s), None value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, 'www', {'type': 'A', 'ttl': 600, 'value': None}
            )
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # empty value, empty string value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {'type': 'A', 'ttl': 600, 'value': ''})
        self.assertEqual(['empty value'], ctx.exception.reasons)

        # missing value(s) & ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'A'})
        self.assertEqual(
            ['missing ttl', 'missing value(s)'], ctx.exception.reasons
        )

        # invalid ipv4 address
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, '', {'type': 'A', 'ttl': 600, 'value': 'hello'}
            )
        self.assertEqual(
            ['invalid IPv4 address "hello"'], ctx.exception.reasons
        )

        # invalid ipv4 addresses
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {'type': 'A', 'ttl': 600, 'values': ['hello', 'goodbye']},
            )
        self.assertEqual(
            ['invalid IPv4 address "hello"', 'invalid IPv4 address "goodbye"'],
            ctx.exception.reasons,
        )

        # invalid & valid ipv4 addresses, no ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {'type': 'A', 'values': ['1.2.3.4', 'hello', '5.6.7.8']},
            )
        self.assertEqual(
            ['missing ttl', 'invalid IPv4 address "hello"'],
            ctx.exception.reasons,
        )
