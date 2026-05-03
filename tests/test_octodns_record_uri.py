#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.rr import RrParseError
from octodns.record.uri import (
    UriNameRfcValidator,
    UriRecord,
    UriValue,
    UriValueRfcValidator,
)
from octodns.zone import Zone


class TestRecordUri(TestCase):
    zone = Zone('unit.tests.', [])

    def test_uri(self):
        a_values = [
            UriValue(
                {
                    'priority': 10,
                    'weight': 11,
                    'target': 'https://server1/foo/bar',
                }
            ),
            UriValue(
                {
                    'priority': 20,
                    'weight': 21,
                    'target': 'https://server2/foo/bar',
                }
            ),
        ]
        a_data = {'ttl': 30, 'values': a_values}
        a = UriRecord(self.zone, '_a._tcp', a_data)
        self.assertEqual('_a._tcp', a.name)
        self.assertEqual('_a._tcp.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values[0]['priority'], a.values[0].priority)
        self.assertEqual(a_values[0]['weight'], a.values[0].weight)
        self.assertEqual(a_values[0]['target'], a.values[0].target)
        self.assertEqual(a_data, a.data)

        b_value = UriValue(
            {'priority': 30, 'weight': 31, 'target': 'ftp://server3/here'}
        )
        b_data = {'ttl': 30, 'value': b_value}
        b = UriRecord(self.zone, '_b._tcp', b_data)
        self.assertEqual(b_value['priority'], b.values[0].priority)
        self.assertEqual(b_value['weight'], b.values[0].weight)
        self.assertEqual(b_value['target'], b.values[0].target)
        self.assertEqual(b_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in priority causes change
        other = UriRecord(
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
        # Diff in target causes change
        other.values[0].target = 'ftp://serverX/there'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_uri_value_rdata_text(self):
        # empty string won't parse
        with self.assertRaises(RrParseError):
            UriValue.parse_rdata_text('')

        # single word won't parse
        with self.assertRaises(RrParseError):
            UriValue.parse_rdata_text('nope')

        # 2nd word won't parse
        with self.assertRaises(RrParseError):
            UriValue.parse_rdata_text('1 2')

        # 4th word won't parse
        with self.assertRaises(RrParseError):
            UriValue.parse_rdata_text('1 2 3 4')

        # priority and weight not ints
        self.assertEqual(
            {
                'priority': 'one',
                'weight': 'two',
                'target': 'http://uri.unit.tests./',
            },
            UriValue.parse_rdata_text('one two "http://uri.unit.tests./"'),
        )

        # valid
        self.assertEqual(
            {'priority': 1, 'weight': 2, 'target': 'http://uri.unit.tests./'},
            UriValue.parse_rdata_text('1 2 "http://uri.unit.tests./"'),
        )

        # quoted
        self.assertEqual(
            {
                'priority': 1,
                'weight': 2,
                'target': 'ftp://uri.unit.tests./there',
            },
            UriValue.parse_rdata_text('1 2 "ftp://uri.unit.tests./there"'),
        )

        zone = Zone('unit.tests.', [])
        a = UriRecord(
            zone,
            '_uri._tcp',
            {
                'ttl': 32,
                'value': {
                    'priority': 1,
                    'weight': 2,
                    'target': 'ssh://uri.unit.tests./',
                },
            },
        )
        self.assertEqual(1, a.values[0].priority)
        self.assertEqual(2, a.values[0].weight)
        self.assertEqual('ssh://uri.unit.tests./', a.values[0].target)
        self.assertEqual('1 2 "ssh://uri.unit.tests./"', a.values[0].rdata_text)

        # both directions should match
        rdata = '1 2 "https://uri.unit.tests./path/to/it"'
        record = UriRecord(
            zone,
            '_uri._tcp',
            {'ttl': 32, 'value': UriValue.parse_rdata_text(rdata)},
        )
        self.assertEqual(rdata, record.values[0].rdata_text)

    def test_uri_value(self):
        a = UriValue({'priority': 0, 'weight': 0, 'target': 'tel:123-123-1234'})
        b = UriValue({'priority': 1, 'weight': 0, 'target': 'tel:123-123-1234'})
        c = UriValue({'priority': 0, 'weight': 2, 'target': 'tel:123-123-1234'})
        e = UriValue({'priority': 0, 'weight': 0, 'target': 'news:mmm.blip'})

        self.assertEqual(a, a)
        self.assertEqual(b, b)
        self.assertEqual(c, c)
        self.assertEqual(e, e)

        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(a, e)
        self.assertNotEqual(b, a)
        self.assertNotEqual(b, c)
        self.assertNotEqual(b, e)
        self.assertNotEqual(c, a)
        self.assertNotEqual(c, b)
        self.assertNotEqual(c, e)
        self.assertNotEqual(e, a)
        self.assertNotEqual(e, b)
        self.assertNotEqual(e, c)

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
            '_uri._tcp',
            {
                'type': 'URI',
                'ttl': 600,
                'value': {
                    'priority': 1,
                    'weight': 2,
                    'target': 'telnet://foo.bar.baz.',
                },
            },
        )

        # permit wildcard entries
        Record.new(
            self.zone,
            '*._tcp',
            {
                'type': 'URI',
                'ttl': 600,
                'value': {
                    'priority': 1,
                    'weight': 2,
                    'target': 'http://food.bar.baz.',
                },
            },
        )

        # invalid name
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'neup',
                {
                    'type': 'URI',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'weight': 2,
                        'target': 'http://foo.bar.baz.',
                    },
                },
            )
        self.assertEqual(['invalid name for URI record'], ctx.exception.reasons)

        # missing priority
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_uri._tcp',
                {
                    'type': 'URI',
                    'ttl': 600,
                    'value': {'weight': 2, 'target': 'blip://foo.bar.baz.'},
                },
            )
        self.assertEqual(['missing priority'], ctx.exception.reasons)

        # invalid priority
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_uri._tcp',
                {
                    'type': 'URI',
                    'ttl': 600,
                    'value': {
                        'priority': 'foo',
                        'weight': 2,
                        'target': 'http://foo.bar.baz.',
                    },
                },
            )
        self.assertEqual(['invalid priority "foo"'], ctx.exception.reasons)

        # missing weight
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_uri._tcp',
                {
                    'type': 'URI',
                    'ttl': 600,
                    'value': {'priority': 1, 'target': 'telnet://foo.bar.baz.'},
                },
            )
        self.assertEqual(['missing weight'], ctx.exception.reasons)
        # invalid weight
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_uri._tcp',
                {
                    'type': 'URI',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'weight': 'foo',
                        'target': 'http://foo.bar.baz.',
                    },
                },
            )
        self.assertEqual(['invalid weight "foo"'], ctx.exception.reasons)

        # missing target
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_uri._tcp',
                {
                    'type': 'URI',
                    'ttl': 600,
                    'value': {'priority': 1, 'weight': 2},
                },
            )
        self.assertEqual(['missing target'], ctx.exception.reasons)
        # invalid target
        # pretty much anything is valid in the general case for a URI

        # falsey target
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '_uri._tcp',
                {
                    'type': 'URI',
                    'ttl': 600,
                    'value': {'priority': 1, 'weight': 2, 'target': ''},
                },
            )
        self.assertEqual(['missing target'], ctx.exception.reasons)

        # target must be a valid URI

    def test_rfc_value_validator_not_in_defaults(self):
        registered = Record.registered_validators()
        uri_value_ids = set(v.id for v in registered['value'].get('URI', []))
        self.assertNotIn('uri-value-rfc', uri_value_ids)

    def test_value_rfc_validator(self):
        validate = UriValueRfcValidator('uri-value-rfc').validate

        # valid
        self.assertEqual(
            [],
            validate(
                UriValue,
                [{'priority': 0, 'weight': 65535, 'target': 'http://x.'}],
                'URI',
            ),
        )

        # priority out of range
        self.assertEqual(
            ['invalid priority "70000"; must be 0-65535'],
            validate(
                UriValue,
                [{'priority': 70000, 'weight': 2, 'target': 'http://x.'}],
                'URI',
            ),
        )

        # weight out of range
        self.assertEqual(
            ['invalid weight "70000"; must be 0-65535'],
            validate(
                UriValue,
                [{'priority': 1, 'weight': 70000, 'target': 'http://x.'}],
                'URI',
            ),
        )

        # priority non-integer
        self.assertEqual(
            ['invalid priority "nope"'],
            validate(
                UriValue,
                [{'priority': 'nope', 'weight': 2, 'target': 'http://x.'}],
                'URI',
            ),
        )

        # weight non-integer
        self.assertEqual(
            ['invalid weight "nope"'],
            validate(
                UriValue,
                [{'priority': 1, 'weight': 'nope', 'target': 'http://x.'}],
                'URI',
            ),
        )

        # missing target
        self.assertEqual(
            ['missing target'],
            validate(UriValue, [{'priority': 1, 'weight': 2}], 'URI'),
        )

        # missing all fields
        self.assertEqual(
            ['missing priority', 'missing weight', 'missing target'],
            validate(UriValue, [{}], 'URI'),
        )

    def test_rfc_value_validator_opt_in(self):
        zone = Zone('unit.tests.', [])
        Record.enable_validators(['legacy'])
        Record.enable_validator('uri-value-rfc', types=['URI'])
        try:
            # priority out of range — only RFC validator catches
            with self.assertRaises(ValidationError) as ctx:
                Record.new(
                    zone,
                    '_uri._tcp',
                    {
                        'type': 'URI',
                        'ttl': 600,
                        'value': {
                            'priority': 70000,
                            'weight': 2,
                            'target': 'http://x.',
                        },
                    },
                )
            self.assertEqual(
                ['invalid priority "70000"; must be 0-65535'],
                ctx.exception.reasons,
            )
            # weight out of range — only RFC validator catches
            with self.assertRaises(ValidationError) as ctx:
                Record.new(
                    zone,
                    '_uri._tcp',
                    {
                        'type': 'URI',
                        'ttl': 600,
                        'value': {
                            'priority': 1,
                            'weight': 70000,
                            'target': 'http://x.',
                        },
                    },
                )
            self.assertEqual(
                ['invalid weight "70000"; must be 0-65535'],
                ctx.exception.reasons,
            )
            # valid passes
            Record.new(
                zone,
                '_uri._tcp',
                {
                    'type': 'URI',
                    'ttl': 600,
                    'value': {
                        'priority': 1,
                        'weight': 2,
                        'target': 'http://x.',
                    },
                },
            )
        finally:
            Record.disable_validator('uri-value-rfc', types=['URI'])

    def test_rfc_name_validator_not_in_defaults(self):
        registered = Record.registered_validators()
        uri_record_ids = set(v.id for v in registered['record'].get('URI', []))
        self.assertNotIn('uri-name-rfc', uri_record_ids)

    def test_name_rfc_validator(self):
        validate = UriNameRfcValidator('uri-name-rfc').validate

        for name in (
            '_ftp._tcp',
            '_http._tcp',
            '_xmpp-client._tcp',
            '_a._tcp',
            '_ftp._tcp.region1',
            '*._tcp',
            '_a1._tcp',
        ):
            self.assertEqual(
                [], validate(UriRecord, name, f'{name}.unit.tests.', {}), name
            )

        # single-label name
        self.assertEqual(
            ['URI name must have at least two labels (_service._proto)'],
            validate(UriRecord, '_ftp', '_ftp.unit.tests.', {}),
        )
        # empty name
        self.assertEqual(
            ['URI name must have at least two labels (_service._proto)'],
            validate(UriRecord, '', 'unit.tests.', {}),
        )

        # service label missing underscore
        self.assertEqual(
            ['invalid URI service label "ftp"'],
            validate(UriRecord, 'ftp._tcp', 'ftp._tcp.unit.tests.', {}),
        )
        # service label too long (>15 chars after underscore)
        long_svc = '_' + ('a' * 16)
        self.assertEqual(
            [f'invalid URI service label "{long_svc}"'],
            validate(
                UriRecord, f'{long_svc}._tcp', f'{long_svc}._tcp.u.t.', {}
            ),
        )
        # service label starts with digit
        self.assertEqual(
            ['invalid URI service label "_1ftp"'],
            validate(UriRecord, '_1ftp._tcp', '_1ftp._tcp.unit.tests.', {}),
        )
        # service label ends with hyphen
        self.assertEqual(
            ['invalid URI service label "_ftp-"'],
            validate(UriRecord, '_ftp-._tcp', '_ftp-._tcp.unit.tests.', {}),
        )
        # service label contains consecutive hyphens
        self.assertEqual(
            ['invalid URI service label "_f--p"'],
            validate(UriRecord, '_f--p._tcp', '_f--p._tcp.unit.tests.', {}),
        )
        # proto label missing underscore
        self.assertEqual(
            ['invalid URI proto label "tcp"'],
            validate(UriRecord, '_ftp.tcp', '_ftp.tcp.unit.tests.', {}),
        )
        # both labels invalid
        self.assertEqual(
            [
                'invalid URI service label "ftp"',
                'invalid URI proto label "tcp"',
            ],
            validate(UriRecord, 'ftp.tcp', 'ftp.tcp.unit.tests.', {}),
        )

    def test_rfc_name_validator_opt_in(self):
        zone = Zone('unit.tests.', [])
        Record.enable_validators(['legacy'])
        Record.enable_validator('uri-name-rfc', types=['URI'])
        try:
            with self.assertRaises(ValidationError) as ctx:
                Record.new(
                    zone,
                    '_1ftp._tcp',
                    {
                        'type': 'URI',
                        'ttl': 600,
                        'value': {
                            'priority': 1,
                            'weight': 2,
                            'target': 'ftp://x.',
                        },
                    },
                )
            self.assertEqual(
                ['invalid URI service label "_1ftp"'], ctx.exception.reasons
            )

            Record.new(
                zone,
                '_ftp._tcp',
                {
                    'type': 'URI',
                    'ttl': 600,
                    'value': {'priority': 1, 'weight': 2, 'target': 'ftp://x.'},
                },
            )
        finally:
            Record.disable_validator('uri-name-rfc', types=['URI'])


class TestUriValue(TestCase):

    def test_template(self):
        value = UriValue(
            {'priority': 10, 'weight': 11, 'target': 'no_placeholders'}
        )
        got = value.template({'needle': 42})
        self.assertIs(value, got)

        value = UriValue(
            {
                'priority': 10,
                'weight': 11,
                'target': 'http://has_{needle}_placeholder/some/path',
            }
        )
        got = value.template({'needle': 42})
        self.assertIsNot(value, got)
        self.assertEqual('http://has_42_placeholder/some/path', got.target)
