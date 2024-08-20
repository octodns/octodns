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
            {'svcpriority': 0, 'targetname': 'foo.example.com.'}
        )
        aliasmode_data = {'ttl': 300, 'value': aliasmode_value}
        a = SvcbRecord(self.zone, 'alias', aliasmode_data)
        self.assertEqual('alias', a.name)
        self.assertEqual('alias.unit.tests.', a.fqdn)
        self.assertEqual(300, a.ttl)
        self.assertEqual(
            aliasmode_value['svcpriority'], a.values[0].svcpriority
        )
        self.assertEqual(aliasmode_value['targetname'], a.values[0].targetname)
        self.assertEqual(aliasmode_value['svcparams'], a.values[0].svcparams)
        self.assertEqual(aliasmode_data, a.data)

        servicemode_values = [
            SvcbValue(
                {
                    'svcpriority': 1,
                    'targetname': 'foo.example.com.',
                    'svcparams': {'port': 8002},
                }
            ),
            SvcbValue(
                {
                    'svcpriority': 2,
                    'targetname': 'foo.example.net.',
                    'svcparams': {'port': 8080},
                }
            ),
        ]
        servicemode_data = {'ttl': 300, 'values': servicemode_values}
        b = SvcbRecord(self.zone, 'service', servicemode_data)
        self.assertEqual('service', b.name)
        self.assertEqual('service.unit.tests.', b.fqdn)
        self.assertEqual(300, b.ttl)
        self.assertEqual(
            servicemode_values[0]['svcpriority'], b.values[0].svcpriority
        )
        self.assertEqual(
            servicemode_values[0]['targetname'], b.values[0].targetname
        )
        self.assertEqual(
            servicemode_values[0]['svcparams'], b.values[0].svcparams
        )
        self.assertEqual(
            servicemode_values[1]['svcpriority'], b.values[1].svcpriority
        )
        self.assertEqual(
            servicemode_values[1]['targetname'], b.values[1].targetname
        )
        self.assertEqual(
            servicemode_values[1]['svcparams'], b.values[1].svcparams
        )
        self.assertEqual(servicemode_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(b.changes(b, target))
        # Diff in priority causes change
        other = SvcbRecord(
            self.zone, 'service2', {'ttl': 30, 'values': servicemode_values}
        )
        other.values[0].svcpriority = 22
        change = b.changes(other, target)
        self.assertEqual(change.existing, b)
        self.assertEqual(change.new, other)
        # Diff in target causes change
        other.values[0].svcpriority = b.values[0].svcpriority
        other.values[0].targetname = 'blabla.example.com.'
        change = b.changes(other, target)
        self.assertEqual(change.existing, b)
        self.assertEqual(change.new, other)
        # Diff in params causes change
        other.values[0].targetname = b.values[0].targetname
        other.values[0].svcparams = {'port': '8888'}
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

        # Double keys are not allowed
        with self.assertRaises(RrParseError):
            SvcbValue.parse_rdata_text('1 foo.example.com port=8080 port=8084')

        # priority not int
        self.assertEqual(
            {
                'svcpriority': 'one',
                'targetname': 'foo.example.com',
                'svcparams': dict(),
            },
            SvcbValue.parse_rdata_text('one foo.example.com'),
        )

        # valid with params
        self.assertEqual(
            {
                'svcpriority': 1,
                'targetname': 'svcb.unit.tests.',
                'svcparams': {'port': '8080', 'no-default-alpn': None},
            },
            SvcbValue.parse_rdata_text(
                '1 svcb.unit.tests. port=8080 no-default-alpn'
            ),
        )

        # quoted target
        self.assertEqual(
            {
                'svcpriority': 1,
                'targetname': 'svcb.unit.tests.',
                'svcparams': dict(),
            },
            SvcbValue.parse_rdata_text('1 "svcb.unit.tests."'),
        )

        zone = Zone('unit.tests.', [])
        a = SvcbRecord(
            zone,
            'svc',
            {
                'ttl': 32,
                'value': {
                    'svcpriority': 1,
                    'targetname': 'svcb.unit.tests.',
                    'svcparams': {'port': '8080'},
                },
            },
        )
        self.assertEqual(1, a.values[0].svcpriority)
        self.assertEqual('svcb.unit.tests.', a.values[0].targetname)
        self.assertEqual({'port': '8080'}, a.values[0].svcparams)

        # both directions should match
        rdata = '1 svcb.unit.tests. no-default-alpn port=8080 ipv4hint=192.0.2.2,192.0.2.53 key3333=foobar'
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

        # quoted params need to be correctly handled
        rdata = '1 svcb.unit.tests. no-default-alpn port=8080 ipv4hint="192.0.2.2,192.0.2.53" key3333="foobar"'
        record = SvcbRecord(
            zone, 'svc', {'ttl': 32, 'value': SvcbValue.parse_rdata_text(rdata)}
        )
        self.assertEqual(rdata.replace('"', ''), record.values[0].rdata_text)

    def test_svcb_value(self):
        a = SvcbValue(
            {'svcpriority': 0, 'targetname': 'foo.', 'svcparams': dict()}
        )
        b = SvcbValue(
            {'svcpriority': 1, 'targetname': 'foo.', 'svcparams': dict()}
        )
        c = SvcbValue(
            {
                'svcpriority': 0,
                'targetname': 'foo.',
                'svcparams': {'port': 8080, 'no-default-alpn': None},
            }
        )
        d = SvcbValue(
            {
                'svcpriority': 0,
                'targetname': 'foo.',
                'svcparams': {'alpn': ['h2', 'h3'], 'port': 8080},
            }
        )
        e = SvcbValue(
            {
                'svcpriority': 0,
                'targetname': 'mmm.',
                'svcparams': {'ipv4hint': ['192.0.2.1']},
            }
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
                'value': {'svcpriority': 1, 'targetname': 'foo.bar.baz.'},
            },
        )

        # Wildcards are fine
        Record.new(
            self.zone,
            '*',
            {
                'type': 'SVCB',
                'ttl': 600,
                'value': {'svcpriority': 1, 'targetname': 'foo.bar.baz.'},
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
                    'value': {'targetname': 'foo.bar.baz.'},
                },
            )
        self.assertEqual(['missing svcpriority'], ctx.exception.reasons)

        # invalid priority
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {
                        'svcpriority': 'foo',
                        'targetname': 'foo.bar.baz.',
                    },
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
                    'value': {
                        'svcpriority': 100000,
                        'targetname': 'foo.bar.baz.',
                    },
                },
            )
        self.assertEqual(['invalid priority "100000"'], ctx.exception.reasons)

        # missing target
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {'type': 'SVCB', 'ttl': 600, 'value': {'svcpriority': 1}},
            )
        self.assertEqual(['missing targetname'], ctx.exception.reasons)

        # invalid target
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {'svcpriority': 1, 'targetname': 'foo.bar.baz'},
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
                    'value': {'svcpriority': 1, 'targetname': ''},
                },
            )
        self.assertEqual(['missing targetname'], ctx.exception.reasons)

        # target must be a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {
                        'svcpriority': 1,
                        'targetname': 'bla foo.bar.com.',
                    },
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
                'value': {'svcpriority': 1, 'targetname': '.'},
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
                        'svcpriority': 0,
                        'targetname': 'foo.bar.com.',
                        'svcparams': {'port': '8000'},
                    },
                },
            )
        self.assertEqual(
            ['svcparams set on AliasMode SVCB record'], ctx.exception.reasons
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
                        'svcpriority': 1,
                        'targetname': 'foo.bar.com.',
                        'svcparams': {'blablabla': '222'},
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
                        'svcpriority': 1,
                        'targetname': 'foo.bar.com.',
                        'svcparams': {'port': 100000},
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
                        'svcpriority': 1,
                        'targetname': 'foo.bar.com.',
                        'svcparams': {'port': 'foo'},
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
                    'svcpriority': 1,
                    'targetname': 'foo.bar.com.',
                    'svcparams': {'no-default-alpn': None},
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
                        'svcpriority': 1,
                        'targetname': 'foo.bar.com.',
                        'svcparams': {'no-default-alpn': 'foobar'},
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
                        'svcpriority': 1,
                        'targetname': 'foo.bar.com.',
                        'svcparams': {'alpn': ['h2', '😅']},
                    },
                },
            )
        self.assertEqual(['non ASCII character in "😅"'], ctx.exception.reasons)

        # svcbvaluelist that is not a list
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {
                        'svcpriority': 1,
                        'targetname': 'foo.bar.com.',
                        'svcparams': {
                            'ipv4hint': '192.0.2.1,192.0.2.2',
                            'ipv6hint': '2001:db8::1',
                            'mandatory': 'ipv6hint',
                            'alpn': 'h2,h3',
                        },
                    },
                },
            )
        self.assertEqual(
            [
                'ipv4hint is not a list',
                'ipv6hint is not a list',
                'mandatory is not a list',
                'alpn is not a list',
            ],
            ctx.exception.reasons,
        )

        # ipv4hint
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'foo',
                {
                    'type': 'SVCB',
                    'ttl': 600,
                    'value': {
                        'svcpriority': 1,
                        'targetname': 'foo.bar.com.',
                        'svcparams': {
                            'ipv4hint': ['192.0.2.0', '500.500.30.30']
                        },
                    },
                },
            )
        self.assertEqual(
            ['ipv4hint "500.500.30.30" is not a valid IPv4 address'],
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
                        'svcpriority': 1,
                        'targetname': 'foo.bar.com.',
                        'svcparams': {
                            'ipv6hint': ['2001:db8:43::1', 'notanip']
                        },
                    },
                },
            )
        self.assertEqual(
            ['ipv6hint "notanip" is not a valid IPv6 address'],
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
                        'svcpriority': 1,
                        'targetname': 'foo.bar.com.',
                        'svcparams': {
                            'mandatory': ['ipv4hint', 'unknown', 'key4444']
                        },
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
                        'svcpriority': 1,
                        'targetname': 'foo.bar.com.',
                        'svcparams': {'ech': ' dG90YWxseUZha2VFQ0hPcHRpb24'},
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
                        'svcpriority': 1,
                        'targetname': 'foo.bar.com.',
                        'svcparams': {
                            'key100000': 'foo',
                            'key3333': 'bar',
                            'keyXXX': 'foo',
                        },
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
