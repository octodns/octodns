#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.rr import RrParseError
from octodns.record.soa import SoaRecord, SoaValue
from octodns.zone import Zone


class TestSoaRecord(TestCase):
    zone = Zone('unit.tests.', [])

    def test_soa(self):
        a_value = SoaValue(
            {
                'mname': 'ns0.unit.tests.',
                'rname': 'hostmaster.unit.tests.',
                'serial': 10,
                'refresh': 86400,
                'retry': 7200,
                'expire': 2419200,
                'minimum': 3600,
            }
        )
        a_data = {'ttl': 3600, 'value': a_value}
        a = SoaRecord(self.zone, '', a_data)
        self.assertEqual('', a.name)
        self.assertEqual('unit.tests.', a.fqdn)
        self.assertEqual(3600, a.ttl)
        self.assertEqual(a_value['mname'], a.value.mname)
        self.assertEqual(a_value['rname'], a.value.rname)
        self.assertEqual(a_value['serial'], a.value.serial)
        self.assertEqual(a_value['refresh'], a.value.refresh)
        self.assertEqual(a_value['retry'], a.value.retry)
        self.assertEqual(a_value['expire'], a.value.expire)
        self.assertEqual(a_value['minimum'], a.value.minimum)
        self.assertEqual(a_data, a.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))

        other = SoaRecord(self.zone, '', {'ttl': 3600, 'value': a_value})

        # Diff in mname causes change
        other.value.mname = 'ns1.unit.tests'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        other.value.mname = a.value.mname

        # Diff in rname causes change
        other.value.rname = 'admin.unit.tests'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        other.value.rname = a.value.rname

        # Diff in serial causes change
        other.value.serial += 1
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        other.value.serial = a.value.serial

        # Diff in refresh causes change
        other.value.refresh += 1
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        other.value.refresh = a.value.refresh

        # Diff in retry causes change
        other.value.retry += 1
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        other.value.retry = a.value.retry

        # Diff in expire causes change
        other.value.expire += 1
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        other.value.expire = a.value.expire

        # Diff in minimum causes change
        other.value.minimum += 1
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        other.value.minimum = a.value.minimum

        # __repr__ doesn't blow up
        a.__repr__()

    def test_soa_value_rdata_text(self):
        # empty string won't parse
        with self.assertRaises(RrParseError):
            SoaValue.parse_rdata_text('')

        # invalid number of words won't parse, SOA needs 7
        with self.assertRaises(RrParseError):
            SoaValue.parse_rdata_text('foo')
        with self.assertRaises(RrParseError):
            SoaValue.parse_rdata_text('1 2')
        with self.assertRaises(RrParseError):
            SoaValue.parse_rdata_text('1 2 3')
        with self.assertRaises(RrParseError):
            SoaValue.parse_rdata_text('1 2 3 4')
        with self.assertRaises(RrParseError):
            SoaValue.parse_rdata_text('1 2 3 4 5')
        with self.assertRaises(RrParseError):
            SoaValue.parse_rdata_text('1 2 3 4 5 6')
        with self.assertRaises(RrParseError):
            SoaValue.parse_rdata_text('1 2 3 4 5 6 7 8')

        # Incrementally check each field
        with self.assertRaisesRegex(RrParseError, 'mname.*FQDN'):
            SoaValue.parse_rdata_text('foo 2 3 4 5 6 7')
        with self.assertRaisesRegex(RrParseError, 'rname.*FQDN'):
            SoaValue.parse_rdata_text('ns0.unit.tests. 2 3 4 5 6 7')
        with self.assertRaisesRegex(RrParseError, 'serial'):
            SoaValue.parse_rdata_text(
                'ns0.unit.tests. hostmaster.unit.tests. nope 4 5 6 7'
            )
        with self.assertRaisesRegex(RrParseError, 'refresh'):
            SoaValue.parse_rdata_text(
                'ns0.unit.tests. hostmaster.unit.tests. 3 nope 5 6 7'
            )
        with self.assertRaisesRegex(RrParseError, 'retry'):
            SoaValue.parse_rdata_text(
                'ns0.unit.tests. hostmaster.unit.tests. 3 4 nope 6 7'
            )
        with self.assertRaisesRegex(RrParseError, 'expire'):
            SoaValue.parse_rdata_text(
                'ns0.unit.tests. hostmaster.unit.tests. 3 4 5 nope 7'
            )
        with self.assertRaisesRegex(RrParseError, 'minimum'):
            SoaValue.parse_rdata_text(
                'ns0.unit.tests. hostmaster.unit.tests. 3 4 5 6 nope'
            )

        self.assertEqual(
            {
                'mname': 'ns0.unit.tests.',
                'rname': 'hostmaster.unit.tests.',
                'serial': 10,
                'refresh': 86400,
                'retry': 7200,
                'expire': 2419200,
                'minimum': 3600,
            },
            SoaValue.parse_rdata_text(
                'ns0.unit.tests. hostmaster.unit.tests. 10 86400 7200 2419200 3600'
            ),
        )

    def test_soa_value(self):
        a = SoaValue(
            {
                'mname': 'ns0.unit.tests.',
                'rname': 'hostmaster.unit.tests.',
                'serial': 10,
                'refresh': 86400,
                'retry': 7200,
                'expire': 2419200,
                'minimum': 3600,
            }
        )
        b = SoaValue(
            {
                'mname': 'ns0.test.units.',
                'rname': 'hostmaster.test.units.',
                'serial': 20,
                'refresh': 186400,
                'retry': 17200,
                'expire': 12419200,
                'minimum': 13600,
            }
        )

        self.assertEqual(a, a)
        self.assertEqual(b, b)

        self.assertNotEqual(a, b)

        # Hash
        values = set()
        values.add(a)
        self.assertTrue(a in values)
        self.assertFalse(b in values)
        values.add(b)
        self.assertTrue(b in values)

    def test_validation(self):
        Record.new(
            self.zone,
            '',
            {
                'type': 'SOA',
                'ttl': 3600,
                'value': {
                    'mname': 'ns0.unit.tests.',
                    'rname': 'hostmaster.unit.tests.',
                    'serial': 10,
                    'refresh': 86400,
                    'retry': 7200,
                    'expire': 2419200,
                    'minimum': 3600,
                },
            },
        )

        # root only
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'nope',
                {
                    'type': 'SOA',
                    'ttl': 3600,
                    'value': {
                        'mname': 'ns0.unit.tests.',
                        'rname': 'hostmaster.unit.tests.',
                        'serial': 10,
                        'refresh': 86400,
                        'retry': 7200,
                        'expire': 2419200,
                        'minimum': 3600,
                    },
                },
            )
        self.assertEqual(['non-root SOA not allowed'], ctx.exception.reasons)

        # missing everything
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'SOA', 'ttl': 3600, 'value': {}})
        self.assertEqual(
            [
                'missing mname',
                'missing rname',
                'missing serial',
                'missing refresh',
                'missing retry',
                'missing expire',
                'missing minimum',
            ],
            ctx.exception.reasons,
        )

        # invalid values
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SOA',
                    'ttl': 3600,
                    'value': {
                        'mname': 'a',
                        'rname': 'b',
                        'serial': 'c',
                        'refresh': 'd',
                        'retry': 'e',
                        'expire': 'f',
                        'minimum': 'g',
                    },
                },
            )
        self.assertEqual(
            [
                'invalid mname',
                'invalid rname',
                'invalid serial',
                'invalid refresh value',
                'invalid retry value',
                'invalid expire value',
                'invalid minimum value',
            ],
            ctx.exception.reasons,
        )


class TestSoaValue(TestCase):

    def test_template(self):
        value = SoaValue(
            {
                'mname': 'ns0.unit.tests.',
                'rname': 'hostmaster.unit.tests.',
                'serial': 10,
                'refresh': 86400,
                'retry': 7200,
                'expire': 2419200,
                'minimum': 3600,
            }
        )
        got = value.template({'needle': 42})
        self.assertIs(value, got)

        value = SoaValue(
            {
                'mname': 'ns0.unit.tests.',
                'rname': '{needle}.unit.tests.',
                'serial': 10,
                'refresh': 86400,
                'retry': 7200,
                'expire': 2419200,
                'minimum': 3600,
            }
        )
        got = value.template({'needle': 'hostmaster'})
        self.assertIsNot(value, got)
        self.assertEqual('hostmaster.unit.tests.', got.rname)
