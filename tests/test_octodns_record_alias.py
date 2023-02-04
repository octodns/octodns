#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.alias import AliasRecord
from octodns.record.exception import ValidationError
from octodns.zone import Zone


class TestRecordAlias(TestCase):
    zone = Zone('unit.tests.', [])

    def test_alias(self):
        a_data = {'ttl': 0, 'value': 'www.unit.tests.'}
        a = AliasRecord(self.zone, '', a_data)
        self.assertEqual('', a.name)
        self.assertEqual('unit.tests.', a.fqdn)
        self.assertEqual(0, a.ttl)
        self.assertEqual(a_data['value'], a.value)
        self.assertEqual(a_data, a.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in value causes change
        other = AliasRecord(self.zone, 'a', a_data)
        other.value = 'foo.unit.tests.'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_alias_lowering_value(self):
        upper_record = AliasRecord(
            self.zone,
            'aliasUppwerValue',
            {'ttl': 30, 'type': 'ALIAS', 'value': 'GITHUB.COM'},
        )
        lower_record = AliasRecord(
            self.zone,
            'aliasLowerValue',
            {'ttl': 30, 'type': 'ALIAS', 'value': 'github.com'},
        )
        self.assertEqual(upper_record.value, lower_record.value)

    def test_validation_and_value_mixin(self):
        # doesn't blow up
        Record.new(
            self.zone,
            '',
            {'type': 'ALIAS', 'ttl': 600, 'value': 'foo.bar.com.'},
        )

        # root only
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'nope',
                {'type': 'ALIAS', 'ttl': 600, 'value': 'foo.bar.com.'},
            )
        self.assertEqual(['non-root ALIAS not allowed'], ctx.exception.reasons)

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'ALIAS', 'ttl': 600})
        self.assertEqual(['missing value'], ctx.exception.reasons)

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, '', {'type': 'ALIAS', 'ttl': 600, 'value': None}
            )
        self.assertEqual(['missing value'], ctx.exception.reasons)

        # empty value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, '', {'type': 'ALIAS', 'ttl': 600, 'value': ''}
            )
        self.assertEqual(['empty value'], ctx.exception.reasons)

        # not a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, '', {'type': 'ALIAS', 'ttl': 600, 'value': '__.'}
            )
        self.assertEqual(
            ['ALIAS value "__." is not a valid FQDN'], ctx.exception.reasons
        )

        # missing trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {'type': 'ALIAS', 'ttl': 600, 'value': 'foo.bar.com'},
            )
        self.assertEqual(
            ['ALIAS value "foo.bar.com" missing trailing .'],
            ctx.exception.reasons,
        )
