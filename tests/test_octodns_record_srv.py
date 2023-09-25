#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.rr import RrParseError
from octodns.record.srv import SrvRecord, SrvValue
from octodns.zone import Zone


class TestRecordSrv(TestCase):
    zone = Zone('unit.tests.', [])

    def test_srv(self):
        a_values = [
            SrvValue(
                {'priority': 10, 'weight': 11, 'port': 12, 'target': 'server1'}
            ),
            SrvValue(
                {'priority': 20, 'weight': 21, 'port': 22, 'target': 'server2'}
            ),
        ]
        a_data = {'ttl': 30, 'values': a_values}
        a = SrvRecord(self.zone, '_a._tcp', a_data)
        self.assertEqual('_a._tcp', a.name)
        self.assertEqual('_a._tcp.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values[0]['priority'], a.values[0].priority)
        self.assertEqual(a_values[0]['weight'], a.values[0].weight)
        self.assertEqual(a_values[0]['port'], a.values[0].port)
        self.assertEqual(a_values[0]['target'], a.values[0].target)
        self.assertEqual(a_data, a.data)

        b_value = SrvValue(
            {'priority': 30, 'weight': 31, 'port': 32, 'target': 'server3'}
        )
        b_data = {'ttl': 30, 'value': b_value}
        b = SrvRecord(self.zone, '_b._tcp', b_data)
        self.assertEqual(b_value['priority'], b.values[0].priority)
        self.assertEqual(b_value['weight'], b.values[0].weight)
        self.assertEqual(b_value['port'], b.values[0].port)
        self.assertEqual(b_value['target'], b.values[0].target)
        self.assertEqual(b_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in priority causes change
        other = SrvRecord(
            self.zone, '_a._icmp', {'ttl': 30, 'values': a_values}
        )
        other.values[0].priority = 22
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in weight causes change
        other.values[0].priority = a.values[0].priority
        other.values[0].weight = 33
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in port causes change
        other.values[0].weight = a.values[0].weight
        other.values[0].port = 44
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in target causes change
        other.values[0].port = a.values[0].port
        other.values[0].target = 'serverX'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_srv_value_rdata_text(self):
        # empty string won't parse
        with self.assertRaises(RrParseError):
            SrvValue.parse_rdata_text('')

        # single word won't parse
        with self.assertRaises(RrParseError):
            SrvValue.parse_rdata_text('nope')

        # 2nd word won't parse
        with self.assertRaises(RrParseError):
            SrvValue.parse_rdata_text('1 2')

        # 3rd word won't parse
        with self.assertRaises(RrParseError):
            SrvValue.parse_rdata_text('1 2 3')

        # 5th word won't parse
        with self.assertRaises(RrParseError):
            SrvValue.parse_rdata_text('1 2 3 4 5')

        # priority weight and port not ints
        self.assertEqual(
            {
                'priority': 'one',
                'weight': 'two',
                'port': 'three',
                'target': 'srv.unit.tests.',
            },
            SrvValue.parse_rdata_text('one two three srv.unit.tests.'),
        )

        # valid
        self.assertEqual(
            {
                'priority': 1,
                'weight': 2,
                'port': 3,
                'target': 'srv.unit.tests.',
            },
            SrvValue.parse_rdata_text('1 2 3 srv.unit.tests.'),
        )

        # quoted
        self.assertEqual(
            {
                'priority': 1,
                'weight': 2,
                'port': 3,
                'target': 'srv.unit.tests.',
            },
            SrvValue.parse_rdata_text('1 2 3 "srv.unit.tests."'),
        )

        zone = Zone('unit.tests.', [])
        a = SrvRecord(
            zone,
            '_srv._tcp',
            {
                'ttl': 32,
                'value': {
                    'priority': 1,
                    'weight': 2,
                    'port': 3,
                    'target': 'srv.unit.tests.',
                },
            },
        )
        self.assertEqual(1, a.values[0].priority)
        self.assertEqual(2, a.values[0].weight)
        self.assertEqual(3, a.values[0].port)
        self.assertEqual('srv.unit.tests.', a.values[0].target)
        self.assertEqual('1 2 3 srv.unit.tests.', a.values[0].rdata_text)

        # both directions should match
        rdata = '1 2 3 srv.unit.tests.'
        record = SrvRecord(
            zone,
            '_srv._tcp',
            {'ttl': 32, 'value': SrvValue.parse_rdata_text(rdata)},
        )
        self.assertEqual(rdata, record.values[0].rdata_text)

    def test_srv_value(self):
        a = SrvValue({'priority': 0, 'weight': 0, 'port': 0, 'target': 'foo.'})
        b = SrvValue({'priority': 1, 'weight': 0, 'port': 0, 'target': 'foo.'})
        c = SrvValue({'priority': 0, 'weight': 2, 'port': 0, 'target': 'foo.'})
        d = SrvValue({'priority': 0, 'weight': 0, 'port': 3, 'target': 'foo.'})
        e = SrvValue({'priority': 0, 'weight': 0, 'port': 0, 'target': 'mmm.'})

        self.assertEqual(a, a)
        self.assertEqual(b, b)
        self.assertEqual(c, c)
        self.assertEqual(d, d)
        self.assertEqual(e, e)

        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(a, d)
        self.assertNotEqual(a, e)
        self.assertNotEqual(b, a)
        self.assertNotEqual(b, c)
        self.assertNotEqual(b, d)
        self.assertNotEqual(b, e)
        self.assertNotEqual(c, a)
        self.assertNotEqual(c, b)
        self.assertNotEqual(c, d)
        self.assertNotEqual(c, e)
        self.assertNotEqual(d, a)
        self.assertNotEqual(d, b)
        self.assertNotEqual(d, c)
        self.assertNotEqual(d, e)
        self.assertNotEqual(e, a)
        self.assertNotEqual(e, b)
        self.assertNotEqual(e, c)
        self.assertNotEqual(e, d)

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

        # Hash
        values = set()
        values.add(a)
        self.assertTrue(a in values)
        self.assertFalse(b in values)
        values.add(b)
        self.assertTrue(b in values)

    def test_valiation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            '_srv._tcp',
            {
                'type': 'SRV',
                'ttl': 600,
                'value': {
                    'priority': 1,
                    'weight': 2,
                    'port': 3,
                    'target': 'foo.bar.baz.',
                },
            },
        )

        # permit wildcard entries
        Record.new(
            self.zone,
            '*._tcp',
            {
                'type': 'SRV',
                'ttl': 600,
                'value': {
                    'priority': 1,
                    'weight': 2,
                    'port': 3,
                    'target': 'food.bar.baz.',
                },
            },
        )

        # invalid name
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'neup',
                {
                    'type': 'SRV',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'weight': 2,
                        'port': 3,
                        'target': 'foo.bar.baz.',
                    },
                },
            )
        self.assertEqual(['invalid name for SRV record'], ctx.exception.reasons)

        # missing priority
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_srv._tcp',
                {
                    'type': 'SRV',
                    'ttl': 600,
                    'value': {'weight': 2, 'port': 3, 'target': 'foo.bar.baz.'},
                },
            )
        self.assertEqual(['missing priority'], ctx.exception.reasons)

        # invalid priority
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_srv._tcp',
                {
                    'type': 'SRV',
                    'ttl': 600,
                    'value': {
                        'priority': 'foo',
                        'weight': 2,
                        'port': 3,
                        'target': 'foo.bar.baz.',
                    },
                },
            )
        self.assertEqual(['invalid priority "foo"'], ctx.exception.reasons)

        # missing weight
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_srv._tcp',
                {
                    'type': 'SRV',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'port': 3,
                        'target': 'foo.bar.baz.',
                    },
                },
            )
        self.assertEqual(['missing weight'], ctx.exception.reasons)
        # invalid weight
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_srv._tcp',
                {
                    'type': 'SRV',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'weight': 'foo',
                        'port': 3,
                        'target': 'foo.bar.baz.',
                    },
                },
            )
        self.assertEqual(['invalid weight "foo"'], ctx.exception.reasons)

        # missing port
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_srv._tcp',
                {
                    'type': 'SRV',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'weight': 2,
                        'target': 'foo.bar.baz.',
                    },
                },
            )
        self.assertEqual(['missing port'], ctx.exception.reasons)
        # invalid port
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_srv._tcp',
                {
                    'type': 'SRV',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'weight': 2,
                        'port': 'foo',
                        'target': 'foo.bar.baz.',
                    },
                },
            )
        self.assertEqual(['invalid port "foo"'], ctx.exception.reasons)

        # missing target
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_srv._tcp',
                {
                    'type': 'SRV',
                    'ttl': 600,
                    'value': {'priority': 1, 'weight': 2, 'port': 3},
                },
            )
        self.assertEqual(['missing target'], ctx.exception.reasons)
        # invalid target
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_srv._tcp',
                {
                    'type': 'SRV',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'weight': 2,
                        'port': 3,
                        'target': 'foo.bar.baz',
                    },
                },
            )
        self.assertEqual(
            ['SRV value "foo.bar.baz" missing trailing .'],
            ctx.exception.reasons,
        )

        # falsey target
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_srv._tcp',
                {
                    'type': 'SRV',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'weight': 2,
                        'port': 3,
                        'target': '',
                    },
                },
            )
        self.assertEqual(['missing target'], ctx.exception.reasons)

        # target must be a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_srv._tcp',
                {
                    'type': 'SRV',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'weight': 2,
                        'port': 3,
                        'target': '100 foo.bar.com.',
                    },
                },
            )
        self.assertEqual(
            ['Invalid SRV target "100 foo.bar.com." is not a valid FQDN.'],
            ctx.exception.reasons,
        )
