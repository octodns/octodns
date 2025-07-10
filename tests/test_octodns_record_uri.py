#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.rr import RrParseError
from octodns.record.uri import UriRecord, UriValue
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
        self.assertTrue(a in values)
        self.assertFalse(b in values)
        values.add(b)
        self.assertTrue(b in values)

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
