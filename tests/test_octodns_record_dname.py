#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.dname import DnameRecord
from octodns.record.exception import ValidationError
from octodns.zone import Zone


class TestRecordDname(TestCase):
    zone = Zone('unit.tests.', [])

    def assertSingleValue(self, _type, a_value, b_value):
        a_data = {'ttl': 30, 'value': a_value}
        a = _type(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_value, a.value)
        self.assertEqual(a_data, a.data)

        b_data = {'ttl': 30, 'value': b_value}
        b = _type(self.zone, 'b', b_data)
        self.assertEqual(b_value, b.value)
        self.assertEqual(b_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in value causes change
        other = _type(self.zone, 'a', {'ttl': 30, 'value': b_value})
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_dname(self):
        self.assertSingleValue(DnameRecord, 'target.foo.com.', 'other.foo.com.')

    def test_dname_lowering_value(self):
        upper_record = DnameRecord(
            self.zone,
            'DnameUppwerValue',
            {'ttl': 30, 'type': 'DNAME', 'value': 'GITHUB.COM'},
        )
        lower_record = DnameRecord(
            self.zone,
            'DnameLowerValue',
            {'ttl': 30, 'type': 'DNAME', 'value': 'github.com'},
        )
        self.assertEqual(upper_record.value, lower_record.value)

    def test_validation(self):
        # A valid DNAME record.
        Record.new(
            self.zone,
            'sub',
            {'type': 'DNAME', 'ttl': 600, 'value': 'foo.bar.com.'},
        )

        # A DNAME record can be present at the zone APEX.
        Record.new(
            self.zone,
            '',
            {'type': 'DNAME', 'ttl': 600, 'value': 'foo.bar.com.'},
        )

        # not a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, 'www', {'type': 'DNAME', 'ttl': 600, 'value': '.'}
            )
        self.assertEqual(
            ['DNAME value "." is not a valid FQDN'], ctx.exception.reasons
        )

        # missing trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'www',
                {'type': 'DNAME', 'ttl': 600, 'value': 'foo.bar.com'},
            )
        self.assertEqual(
            ['DNAME value "foo.bar.com" missing trailing .'],
            ctx.exception.reasons,
        )
