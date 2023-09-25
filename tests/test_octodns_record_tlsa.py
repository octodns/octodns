#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.rr import RrParseError
from octodns.record.tlsa import TlsaRecord, TlsaValue
from octodns.zone import Zone


class TestRecordTlsa(TestCase):
    zone = Zone('unit.tests.', [])

    def test_tlsa(self):
        a_values = [
            TlsaValue(
                {
                    'certificate_usage': 1,
                    'selector': 1,
                    'matching_type': 1,
                    'certificate_association_data': 'ABABABABABABABABAB',
                }
            ),
            TlsaValue(
                {
                    'certificate_usage': 2,
                    'selector': 0,
                    'matching_type': 2,
                    'certificate_association_data': 'ABABABABABABABABAC',
                }
            ),
        ]
        a_data = {'ttl': 30, 'values': a_values}
        a = TlsaRecord(self.zone, 'a', a_data)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual('a', a.name)
        self.assertEqual(30, a.ttl)
        self.assertEqual(
            a_values[0]['certificate_usage'], a.values[0].certificate_usage
        )
        self.assertEqual(a_values[0]['selector'], a.values[0].selector)
        self.assertEqual(
            a_values[0]['matching_type'], a.values[0].matching_type
        )
        self.assertEqual(
            a_values[0]['certificate_association_data'],
            a.values[0].certificate_association_data,
        )

        self.assertEqual(
            a_values[1]['certificate_usage'], a.values[1].certificate_usage
        )
        self.assertEqual(a_values[1]['selector'], a.values[1].selector)
        self.assertEqual(
            a_values[1]['matching_type'], a.values[1].matching_type
        )
        self.assertEqual(
            a_values[1]['certificate_association_data'],
            a.values[1].certificate_association_data,
        )
        self.assertEqual(a_data, a.data)

        b_value = TlsaValue(
            {
                'certificate_usage': 0,
                'selector': 0,
                'matching_type': 0,
                'certificate_association_data': 'AAAAAAAAAAAAAAA',
            }
        )
        b_data = {'ttl': 30, 'value': b_value}
        b = TlsaRecord(self.zone, 'b', b_data)
        self.assertEqual(
            b_value['certificate_usage'], b.values[0].certificate_usage
        )
        self.assertEqual(b_value['selector'], b.values[0].selector)
        self.assertEqual(b_value['matching_type'], b.values[0].matching_type)
        self.assertEqual(
            b_value['certificate_association_data'],
            b.values[0].certificate_association_data,
        )
        self.assertEqual(b_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in certificate_usage causes change
        other = TlsaRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].certificate_usage = 0
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in selector causes change
        other = TlsaRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].selector = 0
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in matching_type causes change
        other = TlsaRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].matching_type = 0
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in certificate_association_data causes change
        other = TlsaRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].certificate_association_data = 'AAAAAAAAAAAAA'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_tsla_value_rdata_text(self):
        # empty string won't parse
        with self.assertRaises(RrParseError):
            TlsaValue.parse_rdata_text('')

        # single word won't parse
        with self.assertRaises(RrParseError):
            TlsaValue.parse_rdata_text('nope')

        # 2nd word won't parse
        with self.assertRaises(RrParseError):
            TlsaValue.parse_rdata_text('1 2')

        # 3rd word won't parse
        with self.assertRaises(RrParseError):
            TlsaValue.parse_rdata_text('1 2 3')

        # 5th word won't parse
        with self.assertRaises(RrParseError):
            TlsaValue.parse_rdata_text('1 2 3 abcd another')

        # non-ints
        self.assertEqual(
            {
                'certificate_usage': 'one',
                'selector': 'two',
                'matching_type': 'three',
                'certificate_association_data': 'abcd',
            },
            TlsaValue.parse_rdata_text('one two three abcd'),
        )

        # valid
        self.assertEqual(
            {
                'certificate_usage': 1,
                'selector': 2,
                'matching_type': 3,
                'certificate_association_data': 'abcd',
            },
            TlsaValue.parse_rdata_text('1 2 3 abcd'),
        )

        # valid
        self.assertEqual(
            {
                'certificate_usage': 1,
                'selector': 2,
                'matching_type': 3,
                'certificate_association_data': 'abcd',
            },
            TlsaValue.parse_rdata_text('1 2 3 "abcd"'),
        )

        zone = Zone('unit.tests.', [])
        a = TlsaRecord(
            zone,
            'tlsa',
            {
                'ttl': 32,
                'value': {
                    'certificate_usage': 2,
                    'selector': 1,
                    'matching_type': 0,
                    'certificate_association_data': 'abcd',
                },
            },
        )
        self.assertEqual(2, a.values[0].certificate_usage)
        self.assertEqual(1, a.values[0].selector)
        self.assertEqual(0, a.values[0].matching_type)
        self.assertEqual('abcd', a.values[0].certificate_association_data)
        self.assertEqual('2 1 0 abcd', a.values[0].rdata_text)

    def test_validation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            '',
            {
                'type': 'TLSA',
                'ttl': 600,
                'value': {
                    'certificate_usage': 0,
                    'selector': 0,
                    'matching_type': 0,
                    'certificate_association_data': 'AAAAAAAAAAAAA',
                },
            },
        )
        # Multi value, second missing certificate usage
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'values': [
                        {
                            'certificate_usage': 0,
                            'selector': 0,
                            'matching_type': 0,
                            'certificate_association_data': 'AAAAAAAAAAAAA',
                        },
                        {
                            'selector': 0,
                            'matching_type': 0,
                            'certificate_association_data': 'AAAAAAAAAAAAA',
                        },
                    ],
                },
            )
            self.assertEqual(
                ['missing certificate_usage'], ctx.exception.reasons
            )

        # missing certificate_association_data
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 0,
                        'selector': 0,
                        'matching_type': 0,
                    },
                },
            )
            self.assertEqual(
                ['missing certificate_association_data'], ctx.exception.reasons
            )

        # missing certificate_usage
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'selector': 0,
                        'matching_type': 0,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(
                ['missing certificate_usage'], ctx.exception.reasons
            )

        # False certificate_usage
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 4,
                        'selector': 0,
                        'matching_type': 0,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(
                'invalid certificate_usage "{value["certificate_usage"]}"',
                ctx.exception.reasons,
            )

        # Invalid certificate_usage
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 'XYZ',
                        'selector': 0,
                        'matching_type': 0,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(
                'invalid certificate_usage "{value["certificate_usage"]}"',
                ctx.exception.reasons,
            )

        # missing selector
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 0,
                        'matching_type': 0,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(['missing selector'], ctx.exception.reasons)

        # False selector
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 0,
                        'selector': 4,
                        'matching_type': 0,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(
                'invalid selector "{value["selector"]}"', ctx.exception.reasons
            )

        # Invalid selector
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 0,
                        'selector': 'XYZ',
                        'matching_type': 0,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(
                'invalid selector "{value["selector"]}"', ctx.exception.reasons
            )

        # missing matching_type
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 0,
                        'selector': 0,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(['missing matching_type'], ctx.exception.reasons)

        # False matching_type
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 0,
                        'selector': 1,
                        'matching_type': 3,
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(
                'invalid matching_type "{value["matching_type"]}"',
                ctx.exception.reasons,
            )

        # Invalid matching_type
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TLSA',
                    'ttl': 600,
                    'value': {
                        'certificate_usage': 0,
                        'selector': 1,
                        'matching_type': 'XYZ',
                        'certificate_association_data': 'AAAAAAAAAAAAA',
                    },
                },
            )
            self.assertEqual(
                'invalid matching_type "{value["matching_type"]}"',
                ctx.exception.reasons,
            )
