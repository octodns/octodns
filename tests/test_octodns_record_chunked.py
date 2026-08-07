#
#
#

import warnings
from unittest import TestCase

import dns.exception
import dns.rdata

from octodns.processor.filter import ValueAllowlistFilter
from octodns.record import RdataParseError, Record, Rr, TxtRecord
from octodns.record.base import _process_value_validators
from octodns.record.chunked import _ChunkedValue, _ChunkedValuesMixin
from octodns.record.spf import SpfRecord
from octodns.record.txt import TxtValue
from octodns.zone import Zone


class TestRecordChunked(TestCase):
    def test_chunked_value_rdata_text(self):
        for s in (
            None,
            '',
            'word',
            42,
            42.43,
            '1.2.3',
            'some.words.that.here',
            '1.2.word.4',
            '1.2.3.4',
            # quotes are not removed
            '"Hello World!"',
        ):
            self.assertEqual(s, _ChunkedValue.parse_rdata_text(s))

        # semi-colons are escaped
        self.assertEqual(
            'Hello\\; World!', _ChunkedValue.parse_rdata_text('Hello; World!')
        )

        # since we're always a string validate and __init__ don't
        # parse_rdata_text

        zone = Zone('unit.tests.', [])
        a = SpfRecord(zone, 'a', {'ttl': 42, 'value': 'some.target.'})
        self.assertEqual('some.target.', a.values[0].rdata_text)
        self.assertEqual(a.chunked_values, a.rr_values)

    def test_chunked_value_rrs(self):
        for value in (
            '',
            'some text',
            'a\\;b',
            'a "quote" and \\ backslash',
            '\x01control',
            'a' * 256,
        ):
            rdata = TxtValue(value).to_rdata_text()
            self.assertEqual(value, TxtValue.from_rdata_text(rdata))

        value = TxtValue('a' * 256)
        rdata = value.to_rdata_text()
        self.assertEqual(
            [255, 1],
            [len(s) for s in dns.rdata.from_text('IN', 'TXT', rdata).strings],
        )

        zone = Zone('unit.tests.', [])
        record = SpfRecord(zone, 'spf', {'ttl': 42, 'value': 'a "quote"'})
        rdata = record.to_rrset().rdatas[0]
        self.assertEqual('"a \\"quote\\""', rdata)
        self.assertEqual('a "quote"', _ChunkedValue.from_rdata_text(rdata))

    def test_chunked_legacy_migration_guidance(self):
        value = TxtValue('Hello \\; World')
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.assertEqual(str(value), value.rdata_text)
            self.assertEqual(
                TxtValue.normalize_raw_text('Hello; World'),
                TxtValue.parse_rdata_text('Hello; World'),
            )
        self.assertEqual(
            [
                '`TxtValue.rdata_text` is DEPRECATED. Use `str(value)` '
                'instead. Will be removed in 2.0.',
                '`TxtValue.parse_rdata_text` is DEPRECATED. Use '
                '`TxtValue.normalize_raw_text()` instead. Will be removed in '
                '2.0.',
            ],
            [str(warning.message) for warning in caught],
        )
        self.assertEqual([__file__, __file__], [w.filename for w in caught])

    def test_chunked_raw_text_conversion(self):
        raw = 'v=DKIM1;k=rsa;s=email'
        for value_type in (TxtValue, _ChunkedValue):
            normalized = value_type.normalize_raw_text(raw)
            self.assertEqual('v=DKIM1\\;k=rsa\\;s=email', normalized)
            self.assertEqual(raw, value_type(normalized).to_raw_text())
            self.assertEqual(
                'ordinary text', value_type('ordinary text').to_raw_text()
            )

    def test_chunked_from_rdata_text_unquoted_compatibility(self):
        for value_type in (TxtValue, _ChunkedValue):
            self.assertEqual(
                'v=spf1 include:_spf.example.com ~all',
                value_type.from_rdata_text(
                    'v=spf1 include:_spf.example.com ~all'
                ),
            )
            self.assertEqual('single', value_type.from_rdata_text('single'))
            self.assertEqual(
                'foo bar', value_type.from_rdata_text('foo\\032bar')
            )
            self.assertEqual('foobar', value_type.from_rdata_text('"foo" bar'))

    def test_chunked_from_rdata_text_semicolon_compatibility(self):
        # An unquoted `;` starts a master-file comment, so parsing wholly
        # unquoted input as presentation text would silently discard the rest
        # of the value. Treat it as legacy raw text instead, the same way
        # unquoted input with spaces is handled.
        for rdata, expected in (
            # bare ; in wholly unquoted input => legacy raw text
            ('v=DKIM1;k=rsa;p=ABCDEF', 'v=DKIM1\\;k=rsa\\;p=ABCDEF'),
            (
                'v=DMARC1; p=reject; rua=mailto:d@example.com',
                'v=DMARC1\\; p=reject\\; rua=mailto:d@example.com',
            ),
            ('v=spf1 include:x.com ~all;', 'v=spf1 include:x.com ~all\\;'),
            (';foo', '\\;foo'),
            # an already-escaped ; is valid presentation text and round trips
            ('v=DKIM1\\;k=rsa\\;p=ABCDEF', 'v=DKIM1\\;k=rsa\\;p=ABCDEF'),
            # quoted input stays presentation format, ; is a literal there
            ('"v=DKIM1;k=rsa;p=ABCDEF"', 'v=DKIM1\\;k=rsa\\;p=ABCDEF'),
            ('"a;b" "c"', 'a\\;bc'),
            # an embedded newline separates tokens without ending the value
            ('a\nb', 'a\nb'),
            ('foo;bar\nbaz', 'foo\\;bar\nbaz'),
            # unchanged behavior, guards against over-correcting
            ('v=spf1 include:x.com ~all', 'v=spf1 include:x.com ~all'),
            ('hello', 'hello'),
            ('"hello"', 'hello'),
            ('"foo" bar', 'foobar'),
            ('""', ''),
        ):
            for value_type in (TxtValue, _ChunkedValue):
                with self.subTest(rdata=rdata, value_type=value_type):
                    self.assertEqual(
                        expected, value_type.from_rdata_text(rdata)
                    )

    def test_chunked_from_rrs_legacy_raw_parity(self):
        # `Record.from_rrs` is deprecated, but must keep behaving the way it
        # did throughout 1.x for the raw, unquoted TXT/SPF text that providers
        # actually hand it. Asserting against `normalize_raw_text` pins the
        # contract itself rather than a value a future change could quietly
        # "update" alongside a regression.
        #
        # NOTE: this holds for unquoted input only. Once quotes appear the
        # input is presentation format and its character-strings concatenate,
        # e.g. `foo "bar"` normalizes to `foo "bar"` but parses to `foobar`.
        zone = Zone('unit.tests.', [])
        for _type in ('TXT', 'SPF'):
            for raw in (
                'v=DKIM1;k=rsa;p=ABCDEF',
                'v=DMARC1; p=reject; rua=mailto:d@example.com',
                'v=spf1 include:_spf.google.com ~all',
                'foo bar',
                'plain',
            ):
                with self.subTest(_type=_type, raw=raw):
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore')
                        record = Record.from_rrs(
                            zone, [Rr('v.unit.tests.', _type, 42, raw)]
                        )[0]
                    self.assertEqual(
                        [_ChunkedValue.normalize_raw_text(raw)], record.values
                    )

    def test_chunked_from_rdata_text_parse_errors(self):
        for value_type in (TxtValue, _ChunkedValue):
            with self.assertRaises(RdataParseError) as ctx:
                value_type.from_rdata_text('"unterminated')
            self.assertIsInstance(
                ctx.exception.__cause__, dns.exception.SyntaxError
            )

            with self.assertRaises(RdataParseError) as ctx:
                value_type.from_rdata_text('"\\255"')
            self.assertIsInstance(ctx.exception.__cause__, UnicodeDecodeError)

    def test_chunked_record_rrs_preserves_legacy_rendering(self):
        record = SpfRecord(
            Zone('unit.tests.', []),
            'spf',
            {'ttl': 42, 'value': 'semi\\; quote " slash \\ middle'},
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            legacy = record.rrs
        self.assertEqual(
            (
                'spf.unit.tests.',
                42,
                'SPF',
                ['"semi\\; quote \\" slash \\ middle"'],
            ),
            legacy,
        )
        self.assertEqual(
            '`Record.rrs` is DEPRECATED. Use `Record.to_rrset()` instead. '
            'Will be removed in 2.0.',
            str(caught[0].message),
        )

        rdata = record.to_rrset().rdatas[0]
        self.assertNotEqual(legacy[3][0], rdata)
        parsed = dns.rdata.from_text('IN', 'TXT', rdata)
        self.assertEqual(
            b'semi; quote " slash \\ middle', b''.join(parsed.strings)
        )

    def test_chunked_new_api_uses_fixed_chunking(self):
        class SmallChunkTxtRecord(TxtRecord):
            CHUNK_SIZE = 8

        record = SmallChunkTxtRecord(
            Zone('unit.tests.', []), 'small', {'ttl': 42, 'value': 'a' * 30}
        )

        self.assertEqual(
            ['"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"'], record.to_rrset().rdatas
        )
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            self.assertEqual(
                ['"aaaaaaaa" "aaaaaaaa" "aaaaaaaa" "aaaaaa"'], record.rrs[3]
            )

    def test_chunked_new_api_does_not_evaluate_rr_values(self):
        class NewChunkedRecord(TxtRecord):
            @property
            def rr_values(self):
                raise AssertionError('rr_values should not be evaluated')

        record = NewChunkedRecord(
            Zone('unit.tests.', []),
            'new',
            {'ttl': 42, 'values': ['one', 'two']},
        )
        self.assertEqual(['"one"', '"two"'], record.to_rrset().rdatas)

    def test_chunked_legacy_rrs_preserves_rr_values_cardinality(self):
        class LegacyRrValuesRecord(TxtRecord):
            @property
            def rr_values(self):
                return [TxtValue('one'), TxtValue('two'), TxtValue('three')]

        record = LegacyRrValuesRecord(
            Zone('unit.tests.', []), 'legacy', {'ttl': 42, 'value': 'ignored'}
        )
        self.assertEqual(['"ignored"'], record.to_rrset().rdatas)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            self.assertEqual(['one', 'two', 'three'], record.rrs[3])

    def test_chunked_legacy_override_uses_historical_receiver(self):
        class LegacyChunkedValue(_ChunkedValue):
            receivers = []

            @property
            def rdata_text(self):
                self.receivers.append(str(self))
                return f'legacy:{self}'

        class LegacyChunkedRecord(_ChunkedValuesMixin, Record):
            _type = 'LEGACYCHUNKED'
            _value_type = LegacyChunkedValue

        Record.register_type(LegacyChunkedRecord)
        record = LegacyChunkedRecord(
            Zone('unit.tests.', []), 'legacy', {'ttl': 42, 'value': 'a "quote"'}
        )
        expected = 'legacy:"a \\"quote\\""'

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.assertEqual([expected], record.to_rrset().rdatas)
        self.assertEqual(
            [
                '`LegacyChunkedValue.rdata_text` is DEPRECATED. Implement '
                '`to_rdata_text()` instead. Will be removed in 2.0.'
            ],
            [str(warning.message) for warning in caught],
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.assertEqual(
                ('legacy.unit.tests.', 42, 'LEGACYCHUNKED', [expected]),
                record.rrs,
            )
        self.assertEqual(
            [
                '`Record.rrs` is DEPRECATED. Use `Record.to_rrset()` instead. '
                'Will be removed in 2.0.',
                '`LegacyChunkedValue.rdata_text` is DEPRECATED. Implement '
                '`to_rdata_text()` instead. Will be removed in 2.0.',
            ],
            [str(warning.message) for warning in caught],
        )
        self.assertEqual(
            ['"a \\"quote\\""', '"a \\"quote\\""'], LegacyChunkedValue.receivers
        )

    def test_lenient_unicode_presentation_round_trip(self):
        for _type in ('SPF', 'TXT'):
            zone = Zone('unit.tests.', [])
            record = Record.new(
                zone,
                _type.lower(),
                {'ttl': 42, 'type': _type, 'value': 'Déjà \\; vu'},
                lenient=True,
            )
            rrset = record.to_rrset()
            self.assertEqual(['"Déjà \\; vu"'], rrset.rdatas)
            self.assertEqual(
                record.data, Record.from_rrset(zone, rrset, lenient=True).data
            )

            # value filters match TXT/SPF on their bare internal text, which is
            # what an operator writes in config, not presentation text
            zone.add_record(record)
            filtered = ValueAllowlistFilter(
                'unicode', ('Déjà \\; vu',)
            ).process_source_zone(zone.copy(), None)
            self.assertEqual([record], list(filtered.records))

            ascii_record = Record.new(
                Zone('unit.tests.', []),
                'ascii',
                {'ttl': 42, 'type': _type, 'value': 'a' * 256},
            )
            rdata = ascii_record.to_rrset().rdatas[0]
            self.assertEqual(
                [255, 1],
                [
                    len(chunk)
                    for chunk in dns.rdata.from_text('IN', 'TXT', rdata).strings
                ],
            )

    def test_lenient_unicode_oversized_character_string(self):
        value = TxtValue('é' * 300)
        rdata = value.to_rdata_text()
        self.assertEqual([255, 45], [len(v) for v in rdata[1:-1].split('" "')])

        with self.assertRaises(RdataParseError) as ctx:
            TxtValue.from_rdata_text(rdata)
        self.assertIsInstance(
            ctx.exception.__cause__, dns.exception.SyntaxError
        )


class TestChunkedValue(TestCase):
    def test_validate(self):
        # valid stuff
        for data in ('a', 'ab', 'abcdefg', 'abc def', 'abc\\; def'):
            self.assertFalse(
                _process_value_validators(_ChunkedValue, data, 'TXT')
            )
            self.assertFalse(
                _process_value_validators(_ChunkedValue, [data], 'TXT')
            )

        # missing
        for data in (None, []):
            self.assertEqual(
                ['missing value(s)'],
                _process_value_validators(_ChunkedValue, data, 'TXT'),
            )

        # unescaped ;
        self.assertEqual(
            ['unescaped ; in "hello; world"'],
            _process_value_validators(_ChunkedValue, 'hello; world', 'TXT'),
        )

        # double escaped ;
        self.assertEqual(
            ['double escaped ; in "hello\\\\; world"'],
            _process_value_validators(_ChunkedValue, 'hello\\\\; world', 'TXT'),
        )

        # non-asci
        self.assertEqual(
            ['non ASCII character in "v=spf1 –all"'],
            _process_value_validators(_ChunkedValue, 'v=spf1 –all', 'TXT'),
        )
        self.assertEqual(
            ['non ASCII character in "Déjà vu"'],
            _process_value_validators(_ChunkedValue, 'Déjà vu', 'TXT'),
        )

        # None values
        for data in ([None], [None, None]):
            self.assertEqual(
                ['missing value(s)'] * len(data),
                _process_value_validators(_ChunkedValue, data, 'TXT'),
            )
        self.assertEqual(
            ['missing value(s)', 'missing value(s)'],
            _process_value_validators(
                _ChunkedValue, [None, 'foo', None], 'TXT'
            ),
        )

    zone = Zone('unit.tests.', [])

    # some hacks to let us work with smaller sizes
    class Base:
        def __init__(self, *args, **kwargs):
            pass

    class SmallerChunkedMixin(_ChunkedValuesMixin, Base):
        CHUNK_SIZE = 8
        _type = 'TXT'
        _value_type = TxtValue

        def __init__(self, values):
            super().__init__(None, None, {'values': values})

    def test_splitting(self):

        for value, expected in (
            # shorter
            ('0123', '"0123"'),
            # exact
            ('01234567', '"01234567"'),
            # simple
            ('0123456789', '"01234567" "89"'),
            # 1 extra
            ('012345678', '"01234567" "8"'),
            # escape in the middle
            ('01234\\;56789', '"01234\\;5" "6789"'),
            # escape before the boundary
            ('012345\\;6789', '"012345\\;" "6789"'),
            # escape after the boundary
            ('01234567\\;89', '"01234567" "\\;89"'),
            # escape spanning the boundary
            ('0123456\\;789', '"0123456" "\\;789"'),
            # multiple escapes at the boundary
            ('012345\\\\;6789', '"012345" "\\\\;6789"'),
            # exact size escape
            ('012345\\;', '"012345\\;"'),
            # spanning ending
            ('0123456\\;', '"0123456" "\\;"'),
        ):
            sc = self.SmallerChunkedMixin(value)
            self.assertEqual([expected], sc.chunked_values)

        sc = self.SmallerChunkedMixin(['0123456789'])
        self.assertEqual(['"01234567" "89"'], sc.chunked_values)

    def test_template(self):
        s = 'this.has.no.templating.'
        value = _ChunkedValue(s)
        got = value.template({'needle': 42})
        self.assertIs(value, got)

        s = 'this.does.{needle}.have.templating.'
        value = _ChunkedValue(s)
        got = value.template({'needle': 42})
        self.assertIsNot(value, got)
        self.assertEqual('this.does.42.have.templating.', got)
