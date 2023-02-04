#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.cname import CnameRecord
from octodns.record.exception import ValidationError
from octodns.zone import Zone


class TestRecordCname(TestCase):
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

    def test_cname(self):
        self.assertSingleValue(CnameRecord, 'target.foo.com.', 'other.foo.com.')

    def test_cname_lowering_value(self):
        upper_record = CnameRecord(
            self.zone,
            'CnameUppwerValue',
            {'ttl': 30, 'type': 'CNAME', 'value': 'GITHUB.COM'},
        )
        lower_record = CnameRecord(
            self.zone,
            'CnameLowerValue',
            {'ttl': 30, 'type': 'CNAME', 'value': 'github.com'},
        )
        self.assertEqual(upper_record.value, lower_record.value)

    def test_validation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            'www',
            {'type': 'CNAME', 'ttl': 600, 'value': 'foo.bar.com.'},
        )

        # root cname is a no-no
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {'type': 'CNAME', 'ttl': 600, 'value': 'foo.bar.com.'},
            )
        self.assertEqual(['root CNAME not allowed'], ctx.exception.reasons)

        # not a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, 'www', {'type': 'CNAME', 'ttl': 600, 'value': '___.'}
            )
        self.assertEqual(
            ['CNAME value "___." is not a valid FQDN'], ctx.exception.reasons
        )

        # missing trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'www',
                {'type': 'CNAME', 'ttl': 600, 'value': 'foo.bar.com'},
            )
        self.assertEqual(
            ['CNAME value "foo.bar.com" missing trailing .'],
            ctx.exception.reasons,
        )

        # doesn't allow urls
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'www',
                {'type': 'CNAME', 'ttl': 600, 'value': 'https://google.com'},
            )
        self.assertEqual(
            ['CNAME value "https://google.com" is not a valid FQDN'],
            ctx.exception.reasons,
        )

        # doesn't allow urls with paths
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'www',
                {
                    'type': 'CNAME',
                    'ttl': 600,
                    'value': 'https://google.com/a/b/c',
                },
            )
        self.assertEqual(
            ['CNAME value "https://google.com/a/b/c" is not a valid FQDN'],
            ctx.exception.reasons,
        )

        # doesn't allow paths
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'www',
                {'type': 'CNAME', 'ttl': 600, 'value': 'google.com/some/path'},
            )
        self.assertEqual(
            ['CNAME value "google.com/some/path" is not a valid FQDN'],
            ctx.exception.reasons,
        )
