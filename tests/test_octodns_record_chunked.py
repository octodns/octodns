#
#
#

from unittest import TestCase

from octodns.record.base import _process_value_validators
from octodns.record.chunked import _ChunkedValue, _ChunkedValuesMixin
from octodns.record.rr import RrParseError
from octodns.record.spf import SpfRecord
from octodns.record.txt import TxtValue
from octodns.zone import Zone


class TestRecordChunked(TestCase):
    def test_chunked_value_rdata_text(self):
        # non-strings, and empty/falsy values, pass through untouched
        for s in (None, '', 42, 42.43):
            self.assertEqual(s, _ChunkedValue.parse_rdata_text(s))

        # a single unquoted token is unambiguous, no quoting needed
        for s in ('word', '1.2.3', '1.2.word.4', '1.2.3.4'):
            self.assertEqual(s, _ChunkedValue.parse_rdata_text(s))

        # quotes are removed
        self.assertEqual(
            'Hello World!', _ChunkedValue.parse_rdata_text('"Hello World!"')
        )

        # multiple quoted character-strings are concatenated/dechunked
        self.assertEqual(
            'HelloWorld!', _ChunkedValue.parse_rdata_text('"Hello" "World!"')
        )

        # escaped double quotes are unescaped
        self.assertEqual(
            'has "quotes" here',
            _ChunkedValue.parse_rdata_text('"has \\"quotes\\" here"'),
        )

        # semi-colons are escaped, whether quoted or not
        self.assertEqual(
            'Hello\\; World!', _ChunkedValue.parse_rdata_text('"Hello; World!"')
        )
        self.assertEqual(
            'Hello\\;World!', _ChunkedValue.parse_rdata_text('Hello;World!')
        )
        # already escaped semi-colons are left alone, not double-escaped
        self.assertEqual(
            'Hello\\; World!',
            _ChunkedValue.parse_rdata_text('"Hello\\; World!"'),
        )

        # nothing but whitespace tokenizes to nothing
        self.assertEqual('', _ChunkedValue.parse_rdata_text('   '))

        # already-processed values pass straight through
        already = TxtValue('some.target.')
        self.assertIs(already, TxtValue.parse_rdata_text(already))

        # multiple unquoted tokens are ambiguous to concatenate, we don't
        # guess
        with self.assertRaises(RrParseError):
            _ChunkedValue.parse_rdata_text('Hello; World!')

        # mixing quoted & unquoted tokens is likewise ambiguous
        with self.assertRaises(RrParseError):
            _ChunkedValue.parse_rdata_text('"quo" ted')

        # unterminated quoted string
        for value in ('"no closing quote', '"no closing \\" quote either'):
            with self.assertRaises(RrParseError):
                _ChunkedValue.parse_rdata_text(value)

        # since we're always a string validate and __init__ don't
        # parse_rdata_text

        zone = Zone('unit.tests.', [])
        a = SpfRecord(zone, 'a', {'ttl': 42, 'value': 'some.target.'})
        self.assertEqual('"some.target."', a.values[0].rdata_text)


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

    def test_process(self):
        # plain/unquoted strings pass through as-is, unstripped, matching
        # the lenient handling of user-authored YAML values
        for v in ('hello world', 'hello  world', ' leading space'):
            self.assertEqual([v], TxtValue.process([v]))

        # a fully quoted string has its outer quotes removed
        self.assertEqual(['hello world'], TxtValue.process(['"hello world"']))

        # multiple quoted chunks are dechunked
        self.assertEqual(
            ['hello world'], TxtValue.process(['"hello" " world"'])
        )

        # values that are already TxtValue instances, e.g. round-tripping
        # through record.data, are left untouched rather than re-processed
        already = TxtValue('"still quoted"')
        self.assertEqual([already], TxtValue.process([already]))
        self.assertIs(already, TxtValue.process([already])[0])

    def test_chunked_custom_size(self):
        # .chunked() defaults to the class-level CHUNK_SIZE
        value = _ChunkedValue('0123456789')
        self.assertEqual('"0123456789"', value.chunked(255))
        self.assertEqual('"0123456789"', value.rdata_text)

        # an explicit chunk_size overrides it
        self.assertEqual('"01234567" "89"', value.chunked(8))
