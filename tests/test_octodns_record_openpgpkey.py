#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.openpgpkey import OpenpgpkeyRecord, OpenpgpkeyValue
from octodns.zone import Zone


class TestRecordOpenpgpkey(TestCase):
    zone = Zone('unit.tests.', [])

    def test_openpgpkey(self):
        a_values = ['mQINBF...base64...==', 'mQINBG...base64...==']
        a_data = {'ttl': 30, 'values': a_values}
        a = OpenpgpkeyRecord(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values, a.values)
        self.assertEqual(a_data, a.data)

        b_value = 'mQINBF...single...=='
        b_data = {'ttl': 30, 'value': b_value}
        b = OpenpgpkeyRecord(self.zone, 'b', b_data)
        self.assertEqual([b_value], b.values)
        self.assertEqual(b_data, b.data)

    def test_openpgpkey_value_rdata_text(self):
        # parse_rdata_text strips spaces (zone files may split base64)
        self.assertEqual('abc123', OpenpgpkeyValue.parse_rdata_text('abc 123'))
        self.assertEqual(
            'abc123def', OpenpgpkeyValue.parse_rdata_text('abc 123 def')
        )
        self.assertEqual(
            'nospaces', OpenpgpkeyValue.parse_rdata_text('nospaces')
        )

        zone = Zone('unit.tests.', [])
        a = OpenpgpkeyRecord(
            zone, 'a', {'ttl': 42, 'value': 'mQINBF...base64...=='}
        )
        self.assertEqual('mQINBF...base64...==', a.values[0].rdata_text)

    def test_validation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            '',
            {
                'type': 'OPENPGPKEY',
                'ttl': 600,
                'values': ['key1base64==', 'key2base64=='],
            },
        )

        # single value works
        Record.new(
            self.zone,
            '',
            {'type': 'OPENPGPKEY', 'ttl': 600, 'value': 'keybase64=='},
        )

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'OPENPGPKEY', 'ttl': 600})
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # empty values list
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, '', {'type': 'OPENPGPKEY', 'ttl': 600, 'values': []}
            )
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

    def test_changes(self):
        target = SimpleProvider()

        # test change detection - same record
        a = OpenpgpkeyRecord(
            self.zone, 'a', {'ttl': 30, 'value': 'mQINBF...base64...=='}
        )
        self.assertFalse(a.changes(a, target))

        # different value
        b = OpenpgpkeyRecord(
            self.zone, 'a', {'ttl': 30, 'value': 'different...base64...=='}
        )
        self.assertTrue(a.changes(b, target))

        # different ttl
        c = OpenpgpkeyRecord(
            self.zone, 'a', {'ttl': 60, 'value': 'mQINBF...base64...=='}
        )
        self.assertTrue(a.changes(c, target))


class TestOpenpgpkeyValue(TestCase):

    def test_template(self):
        s = 'this.has.no.templating'
        value = OpenpgpkeyValue(s)
        got = value.template({'needle': 42})
        self.assertIs(value, got)

        s = 'this.does.{needle}.have.templating'
        value = OpenpgpkeyValue(s)
        got = value.template({'needle': 42})
        self.assertIsNot(value, got)
        self.assertEqual('this.does.42.have.templating', got)
