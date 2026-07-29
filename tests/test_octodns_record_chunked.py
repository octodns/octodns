#
#
#

import warnings
from unittest import TestCase

from octodns.record.base import _process_value_validators
from octodns.record.chunked import _ChunkedValue, _ChunkedValuesMixin
from octodns.record.rr import RrParseError
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
        with warnings.catch_warnings(record=True):
            warnings.simplefilter('ignore')
            self.assertEqual('some.target.', a.values[0].rdata_text)

    def test_rdata_text_deprecated(self):
        value = TxtValue('some.target.')
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.assertEqual('some.target.', value.rdata_text)
        matched = [
            w
            for w in caught
            if issubclass(w.category, DeprecationWarning)
            and 'TxtValue.rdata_text' in str(w.message)
            and 'to_rrs' in str(w.message)
        ]
        self.assertTrue(matched)

    def test_parse_rdata_text_deprecated(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.assertEqual(
                'Hello\\; World!',
                _ChunkedValue.parse_rdata_text('Hello; World!'),
            )
        matched = [
            w
            for w in caught
            if issubclass(w.category, DeprecationWarning)
            and '_ChunkedValue.parse_rdata_text' in str(w.message)
            and 'from_rrs' in str(w.message)
        ]
        self.assertTrue(matched)


class TestChunkedValueToRrs(TestCase):
    def test_to_rrs(self):
        for value, expected in (
            ('hello world', '"hello world"'),
            # quotes are escaped
            ('has "quotes"', '"has \\"quotes\\""'),
            # backslashes are escaped
            ('back\\slash', '"back\\\\slash"'),
            # octoDNS's internal `\;` escaping is unescaped to a bare `;`
            # since it needs no escaping inside a quoted character-string
            ('semi\\;colon', '"semi;colon"'),
            # non-ASCII/control bytes are rendered as \DDD decimal escapes
            ('Déjà vu', '"D\\195\\169j\\195\\160 vu"'),
            ('ctrl\x01byte', '"ctrl\\001byte"'),
            # empty value
            ('', '""'),
            # exactly 255 bytes: single character-string
            ('a' * 255, f'"{"a" * 255}"'),
            # 256 bytes: splits into two character-strings
            ('a' * 256, f'"{"a" * 255}" "a"'),
        ):
            self.assertEqual(expected, TxtValue(value).to_rrs())

    def test_from_rrs(self):
        for rdata, expected in (
            ('"hello world"', 'hello world'),
            ('"has \\"quotes\\""', 'has "quotes"'),
            ('"back\\\\slash"', 'back\\slash'),
            # a literal `;` in presentation text is restored to octoDNS's
            # internal `\;` escaping
            ('"semi;colon"', 'semi\\;colon'),
            ('"D\\195\\169j\\195\\160 vu"', 'Déjà vu'),
            ('"ctrl\\001byte"', 'ctrl\x01byte'),
            ('""', ''),
            # multiple character-strings concatenate into one raw value
            ('"foo" "bar"', 'foobar'),
        ):
            self.assertEqual(expected, _ChunkedValue.from_rrs(rdata))

    def test_from_rrs_invalid(self):
        with self.assertRaises(RrParseError):
            _ChunkedValue.from_rrs('not a valid txt "')

    def test_round_trip(self):
        for value in (
            'hello world',
            'semi\\;colon',
            'has "quotes" and back\\\\slash',
            'a' * 500,
            '',
        ):
            v = TxtValue(value)
            self.assertEqual(value, _ChunkedValue.from_rrs(v.to_rrs()))


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
