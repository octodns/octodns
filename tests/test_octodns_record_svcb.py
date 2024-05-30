#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.rr import RrParseError
from octodns.record.svcb import SvcbRecord, SvcbValue
from octodns.zone import Zone


class TestRecordSvcb(TestCase):
    zone = Zone('unit.tests.', [])

    def test_svcb(self):
        aliasmode_value = SvcbValue(
            {'priority': 0, 'target': 'foo.example.com.'}
        )
        aliasmode_data = {'ttl': 300, 'value': aliasmode_value}
        a = SvcbRecord(self.zone, 'alias', aliasmode_data)
        self.assertEqual('alias', a.name)
        self.assertEqual('alias.unit.tests.', a.fqdn)
        self.assertEqual(300, a.ttl)
        self.assertEqual(aliasmode_value['priority'], a.values[0].priority)
        self.assertEqual(aliasmode_value['target'], a.values[0].target)
        self.assertEqual(aliasmode_value['params'], a.values[0].params)
        self.assertEqual(aliasmode_data, a.data)

        servicemode_values = [
            SvcbValue(
                {
                    'priority': 1,
                    'target': 'foo.example.com.',
                    'params': 'port=8002',
                }
            ),
            SvcbValue(
                {
                    'priority': 2,
                    'target': 'foo.example.net.',
                    'params': 'port=8080',
                }
            ),
        ]
        servicemode_data = {'ttl': 300, 'values': servicemode_values}
        b = SvcbRecord(self.zone, 'service', servicemode_data)
        self.assertEqual('service', b.name)
        self.assertEqual('service.unit.tests.', b.fqdn)
        self.assertEqual(300, b.ttl)
        self.assertEqual(
            servicemode_values[0]['priority'], b.values[0].priority
        )
        self.assertEqual(servicemode_values[0]['target'], b.values[0].target)
        self.assertEqual(servicemode_values[0]['params'], b.values[0].params)
        self.assertEqual(
            servicemode_values[1]['priority'], b.values[1].priority
        )
        self.assertEqual(servicemode_values[1]['target'], b.values[1].target)
        self.assertEqual(servicemode_values[1]['params'], b.values[1].params)
        self.assertEqual(servicemode_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(b.changes(b, target))
        # Diff in priority causes change
        other = SvcbRecord(
            self.zone, 'service2', {'ttl': 30, 'values': servicemode_values}
        )
        other.values[0].priority = 22
        change = b.changes(other, target)
        self.assertEqual(change.existing, b)
        self.assertEqual(change.new, other)
        # Diff in target causes change
        other.values[0].priority = b.values[0].priority
        other.values[0].target = 'blabla.example.com'
        change = b.changes(other, target)
        self.assertEqual(change.existing, b)
        self.assertEqual(change.new, other)
        # Diff in params causes change
        other.values[0].target = b.values[0].target
        other.values[0].params = 'port=8888'
        change = b.changes(other, target)
        self.assertEqual(change.existing, b)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()
        b.__repr__()

    def test_svcb_value_rdata_text(self):
        # empty string won't parse
        with self.assertRaises(RrParseError):
            SvcbValue.parse_rdata_text('')

        # single word won't parse
        with self.assertRaises(RrParseError):
            SvcbValue.parse_rdata_text('nope')

        # priority not int
        self.assertEqual(
            {'priority': 'one', 'target': 'foo.example.com', 'params': list()},
            SvcbValue.parse_rdata_text('one foo.example.com'),
        )

        # valid with params
        self.assertEqual(
            {
                'priority': 1,
                'target': 'svcb.unit.tests.',
                'params': ['port=8080'],
            },
            SvcbValue.parse_rdata_text('1 svcb.unit.tests. port=8080'),
        )

        # quoted target
        self.assertEqual(
            {'priority': 1, 'target': 'svcb.unit.tests.', 'params': list()},
            SvcbValue.parse_rdata_text('1 "svcb.unit.tests."'),
        )

        zone = Zone('unit.tests.', [])
        a = SvcbRecord(
            zone,
            'svc',
            {
                'ttl': 32,
                'value': {
                    'priority': 1,
                    'target': 'svcb.unit.tests.',
                    'params': ['port=8080'],
                },
            },
        )
        self.assertEqual(1, a.values[0].priority)
        self.assertEqual('svcb.unit.tests.', a.values[0].target)
        self.assertEqual(['port=8080'], a.values[0].params)

        # both directions should match
        rdata = '1 svcb.unit.tests. port=8080'
        record = SvcbRecord(
            zone, 'svc', {'ttl': 32, 'value': SvcbValue.parse_rdata_text(rdata)}
        )
        self.assertEqual(rdata, record.values[0].rdata_text)

        # both directions should match
        rdata = '0 svcb.unit.tests.'
        record = SvcbRecord(
            zone, 'svc', {'ttl': 32, 'value': SvcbValue.parse_rdata_text(rdata)}
        )
        self.assertEqual(rdata, record.values[0].rdata_text)

    def test_svcb_value(self):
        a = SvcbValue({'priority': 0, 'target': 'foo.', 'params': list()})
        b = SvcbValue({'priority': 1, 'target': 'foo.', 'params': list()})
        c = SvcbValue(
            {'priority': 0, 'target': 'foo.', 'params': ['port=8080']}
        )
        d = SvcbValue(
            {
                'priority': 0,
                'target': 'foo.',
                'params': ['alpn=h2,h3', 'port=8080'],
            }
        )
        e = SvcbValue(
            {'priority': 0, 'target': 'mmm.', 'params': ['ipv4hint=192.0.2.1']}
        )

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

    def test_validation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            'svcb',
            {
                'type': 'SVCB',
                'ttl': 600,
                'value': {'priority': 1, 'target': 'foo.bar.baz.'},
            },
        )

        # Wildcards are fine
        Record.new(
            self.zone,
            '*',
            {
                'type': 'SVCB',
                'ttl': 600,
                'value': {'priority': 1, 'target': 'foo.bar.baz.'},
            },
        )

        # missing priority
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {'target': 'foo.bar.baz.'},
                },
            )
        self.assertEqual(['missing priority'], ctx.exception.reasons)

        # invalid priority
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {'priority': 'foo', 'target': 'foo.bar.baz.'},
                },
            )
        self.assertEqual(['invalid priority "foo"'], ctx.exception.reasons)

        # invalid priority (out of range)
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {'priority': 100000, 'target': 'foo.bar.baz.'},
                },
            )
        self.assertEqual(['invalid priority "100000"'], ctx.exception.reasons)

        # missing target
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {'type': 'SVCB', 'ttl': 600, 'value': {'priority': 1}},
            )
        self.assertEqual(['missing target'], ctx.exception.reasons)

        # invalid target
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {'priority': 1, 'target': 'foo.bar.baz'},
                },
            )
        self.assertEqual(
            ['SVCB value "foo.bar.baz" missing trailing .'],
            ctx.exception.reasons,
        )

        # falsey target
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {'priority': 1, 'target': ''},
                },
            )
        self.assertEqual(['missing target'], ctx.exception.reasons)

        # target must be a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {'priority': 1, 'target': 'bla foo.bar.com.'},
                },
            )
        self.assertEqual(
            ['Invalid SVCB target "bla foo.bar.com." is not a valid FQDN.'],
            ctx.exception.reasons,
        )

        # target can be root label
        Record.new(
            self.zone,
            'foo',
            {
                'type': 'SVCB',
                'ttl': 600,
                'value': {'priority': 1, 'target': '.'},
            },
        )

        # Params can't be set for AliasMode
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {
                        'priority': 0,
                        'target': 'foo.bar.com.',
                        'params': ['port=8000'],
                    },
                },
            )
        self.assertEqual(
            ['params set on AliasMode SVCB record'], ctx.exception.reasons
        )

        # Unknown param
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'target': 'foo.bar.com.',
                        'params': ['blablabla=222'],
                    },
                },
            )
        self.assertEqual(['Unknown SvcParam blablabla'], ctx.exception.reasons)

        # Port number invalid
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'target': 'foo.bar.com.',
                        'params': ['port=100000'],
                    },
                },
            )
        self.assertEqual(
            ['port 100000 is not a valid number'], ctx.exception.reasons
        )

        # Port number not an int
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'target': 'foo.bar.com.',
                        'params': ['port=foo'],
                    },
                },
            )
        self.assertEqual(['port is not a number'], ctx.exception.reasons)

        # no-default-alpn set
        Record.new(
            self.zone,
            'foo',
            {
                'type': 'SVCB',
                'ttl': 600,
                'value': {
                    'priority': 1,
                    'target': 'foo.bar.com.',
                    'params': ['no-default-alpn'],
                },
            },
        )

        # no-default-alpn has value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'target': 'foo.bar.com.',
                        'params': ['no-default-alpn=foobar'],
                    },
                },
            )
        self.assertEqual(
            ['SvcParam no-default-alpn has value when it should not'],
            ctx.exception.reasons,
        )

        # alpn is broken
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'target': 'foo.bar.com.',
                        'params': ['alpn=h2,😅'],
                    },
                },
            )
        self.assertEqual(['non ASCII character in "😅"'], ctx.exception.reasons)

        # ipv4hint
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'target': 'foo.bar.com.',
                        'params': ['ipv4hint=192.0.2.0,500.500.30.30'],
                    },
                },
            )
        self.assertEqual(
            ['ip4hint "500.500.30.30" is not a valid IPv4 address'],
            ctx.exception.reasons,
        )

        # ipv6hint
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'target': 'foo.bar.com.',
                        'params': ['ipv6hint=2001:db8:43::1,notanip'],
                    },
                },
            )
        self.assertEqual(
            ['ip6hint "notanip" is not a valid IPv6 address'],
            ctx.exception.reasons,
        )

        # mandatory
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'target': 'foo.bar.com.',
                        'params': ['mandatory=ipv4hint,unknown,key4444'],
                    },
                },
            )
        self.assertEqual(
            ['unsupported SvcParam "unknown" in mandatory'],
            ctx.exception.reasons,
        )

        # ech
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'target': 'foo.bar.com.',
                        'params': ['ech=dG90YWxseUZha2VFQ0hPcHRpb24'],
                    },
                },
            )
        self.assertEqual(
            ['ech SvcParam is invalid Base64'], ctx.exception.reasons
        )

        # broken keyNNNN format
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'target': 'foo.bar.com.',
                        'params': [
                            'key100000=foo',
                            'key3333=bar',
                            'keyXXX=foo',
                        ],
                    },
                },
            )
        self.assertEqual(
            [
                'SvcParam key "key100000" has wrong key number',
                'SvcParam key "keyXXX" has wrong format',
            ],
            ctx.exception.reasons,
        )
