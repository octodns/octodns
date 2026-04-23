#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.processor.templating import Templating
from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.rr import RrParseError
from octodns.record.srv import (
    SrvRecord,
    SrvStrictNameValidator,
    SrvStrictValueValidator,
    SrvValue,
)
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
        self.assertIn(a, values)
        self.assertNotIn(b, values)
        values.add(b)
        self.assertIn(b, values)

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
            ['SRV target "foo.bar.baz" missing trailing .'],
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
            ['SRV target "100 foo.bar.com." is not a valid FQDN'],
            ctx.exception.reasons,
        )


class TestSrvValue(TestCase):

    def test_template(self):
        value = SrvValue(
            {
                'priority': 10,
                'weight': 11,
                'port': 12,
                'target': 'no_placeholders',
            }
        )
        got = value.template({'needle': 42})
        self.assertIs(value, got)

        value = SrvValue(
            {
                'priority': 10,
                'weight': 11,
                'port': 12,
                'target': 'has_{needle}_placeholder',
            }
        )
        got = value.template({'needle': 42})
        self.assertIsNot(value, got)
        self.assertEqual('has_42_placeholder', got.target)

    def test_strict_name_validator_not_in_defaults(self):
        # confirm the strict validators are opt-in and not on the record/value
        # classes by default
        self.assertNotIn(SrvStrictNameValidator, SrvRecord.VALIDATORS)
        self.assertNotIn(SrvStrictValueValidator, SrvValue.VALIDATORS)

    def test_strict_name_validator(self):
        validate = SrvStrictNameValidator.validate

        # valid names
        for name in (
            '_sip._tcp',
            '_http._tcp',
            '_xmpp-client._tcp',
            '_a._tcp',
            '_sip._tcp.region1',
            '*._tcp',
            '_a1._tcp',
        ):
            self.assertEqual(
                [], validate(SrvRecord, name, f'{name}.unit.tests.', {}), name
            )

        # single-label name
        self.assertEqual(
            ['SRV name must have at least two labels (_service._proto)'],
            validate(SrvRecord, '_sip', '_sip.unit.tests.', {}),
        )
        # empty name
        self.assertEqual(
            ['SRV name must have at least two labels (_service._proto)'],
            validate(SrvRecord, '', 'unit.tests.', {}),
        )

        # service label missing underscore
        self.assertEqual(
            ['invalid SRV service label "sip"'],
            validate(SrvRecord, 'sip._tcp', 'sip._tcp.unit.tests.', {}),
        )
        # service label too long (>15 chars after underscore)
        long_svc = '_' + ('a' * 16)
        self.assertEqual(
            [f'invalid SRV service label "{long_svc}"'],
            validate(
                SrvRecord, f'{long_svc}._tcp', f'{long_svc}._tcp.u.t.', {}
            ),
        )
        # service label starts with digit
        self.assertEqual(
            ['invalid SRV service label "_1sip"'],
            validate(SrvRecord, '_1sip._tcp', '_1sip._tcp.u.t.', {}),
        )
        # service label ends with hyphen
        self.assertEqual(
            ['invalid SRV service label "_sip-"'],
            validate(SrvRecord, '_sip-._tcp', '_sip-._tcp.u.t.', {}),
        )
        # service label has consecutive hyphens
        self.assertEqual(
            ['invalid SRV service label "_si--p"'],
            validate(SrvRecord, '_si--p._tcp', '_si--p._tcp.u.t.', {}),
        )
        # service label with illegal char
        self.assertEqual(
            ['invalid SRV service label "_si$p"'],
            validate(SrvRecord, '_si$p._tcp', '_si$p._tcp.u.t.', {}),
        )
        # empty service body (just underscore)
        self.assertEqual(
            ['invalid SRV service label "_"'],
            validate(SrvRecord, '_._tcp', '_._tcp.u.t.', {}),
        )

        # proto label missing underscore
        self.assertEqual(
            ['invalid SRV proto label "tcp"'],
            validate(SrvRecord, '_sip.tcp', '_sip.tcp.u.t.', {}),
        )
        # proto label invalid body
        self.assertEqual(
            ['invalid SRV proto label "_1tcp"'],
            validate(SrvRecord, '_sip._1tcp', '_sip._1tcp.u.t.', {}),
        )

        # both service and proto wrong -> two reasons
        reasons = validate(SrvRecord, 'sip.tcp', 'sip.tcp.u.t.', {})
        self.assertEqual(
            [
                'invalid SRV service label "sip"',
                'invalid SRV proto label "tcp"',
            ],
            reasons,
        )

    def test_strict_value_validator(self):
        validate = SrvStrictValueValidator.validate

        # valid values, including null-target convention
        good = [
            {'priority': 10, 'weight': 20, 'port': 443, 'target': 'h.u.t.'},
            {'priority': 0, 'weight': 0, 'port': 0, 'target': '.'},
            {'priority': 65535, 'weight': 65535, 'port': 65535, 'target': 'h.'},
        ]
        self.assertEqual([], validate(SrvValue, good, 'SRV'))

        # out of range, low
        self.assertEqual(
            ['priority "-1" out of range 0-65535'],
            validate(
                SrvValue,
                [{'priority': -1, 'weight': 1, 'port': 80, 'target': 'h.'}],
                'SRV',
            ),
        )

        # out of range, high on all three
        reasons = validate(
            SrvValue,
            [
                {
                    'priority': 65536,
                    'weight': 70000,
                    'port': 99999,
                    'target': 'h.',
                }
            ],
            'SRV',
        )
        self.assertEqual(
            [
                'priority "65536" out of range 0-65535',
                'weight "70000" out of range 0-65535',
                'port "99999" out of range 0-65535',
            ],
            reasons,
        )

        # non-zero values with target "." should be flagged
        reasons = validate(
            SrvValue,
            [{'priority': 1, 'weight': 2, 'port': 3, 'target': '.'}],
            'SRV',
        )
        self.assertEqual(
            [
                'priority must be 0 when target is "."',
                'weight must be 0 when target is "."',
                'port must be 0 when target is "."',
            ],
            reasons,
        )

        # port 0 with non-null target
        self.assertEqual(
            ['port 0 is reserved; must be > 0 when target is not "."'],
            validate(
                SrvValue,
                [{'priority': 10, 'weight': 10, 'port': 0, 'target': 'h.'}],
                'SRV',
            ),
        )

        # missing/non-int fields are silently skipped (base validator owns
        # those reasons)
        self.assertEqual(
            [],
            validate(
                SrvValue,
                [
                    {
                        'priority': 'nope',
                        'weight': 10,
                        'port': 80,
                        'target': 'h.',
                    },
                    {'priority': 10, 'port': 80, 'target': 'h.'},
                ],
                'SRV',
            ),
        )

    def test_strict_validators_opt_in(self):
        # wire both strict validators onto the classes so we exercise them
        # end-to-end through Record.new, then clean up.
        zone = Zone('unit.tests.', [])
        SrvRecord.VALIDATORS = SrvRecord.VALIDATORS + [SrvStrictNameValidator]
        SrvValue.VALIDATORS = SrvValue.VALIDATORS + [SrvStrictValueValidator]
        try:
            with self.assertRaises(ValidationError) as ctx:
                Record.new(
                    zone,
                    '_1sip._tcp',
                    {
                        'type': 'SRV',
                        'ttl': 600,
                        'value': {
                            'priority': 1,
                            'weight': 2,
                            'port': 70000,
                            'target': 'foo.bar.',
                        },
                    },
                )
            self.assertEqual(
                [
                    'port "70000" out of range 0-65535',
                    'invalid SRV service label "_1sip"',
                ],
                ctx.exception.reasons,
            )

            # valid record with strict validators enabled passes
            Record.new(
                zone,
                '_sip._tcp',
                {
                    'type': 'SRV',
                    'ttl': 600,
                    'value': {
                        'priority': 0,
                        'weight': 0,
                        'port': 0,
                        'target': '.',
                    },
                },
            )
        finally:
            SrvRecord.VALIDATORS = [
                v
                for v in SrvRecord.VALIDATORS
                if v is not SrvStrictNameValidator
            ]
            SrvValue.VALIDATORS = [
                v
                for v in SrvValue.VALIDATORS
                if v is not SrvStrictValueValidator
            ]

    def test_template_validation(self):
        templ = Templating('test')

        zone = Zone('unit.tests.', [])
        srv = Record.new(
            zone,
            '_srv._tcp',
            {
                'type': 'SRV',
                'ttl': 1800,
                # Only the "target" field can be templated.
                'value': {
                    'priority': 1,
                    'weight': 2,
                    'port': 3,
                    'target': '{zone_name}example.com.',
                },
            },
            lenient=False,
        )
        zone.add_record(srv)

        # Should not raise any ValidationError related to the templating
        # variables as target value validation must takes place after variables
        # substitution.
        templ.process_source_and_target_zones(zone, None, None)

        srv = Record.new(
            zone,
            '_srv._tcp',
            {
                'type': 'SRV',
                'ttl': 1800,
                'value': {
                    'priority': 1,
                    'weight': 2,
                    'port': 3,
                    # "{zone_name}" is already ending with a dot.
                    'target': '{zone_name}.example.com.',
                },
            },
            lenient=False,
        )
        zone.add_record(srv, replace=True)

        with self.assertRaises(ValidationError) as ctx:
            templ.process_source_and_target_zones(zone, None, None)
        self.assertEqual(
            ['SRV target "unit.tests..example.com." is not a valid FQDN'],
            ctx.exception.reasons,
        )
