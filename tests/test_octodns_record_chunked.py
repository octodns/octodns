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

        # semi-colons inside quotes are escaped (marked) per octoDNS's own
        # convention -- RFC-wise a bare ; needs no escaping inside quotes,
        # this is purely octoDNS's internal representation
        self.assertEqual(
            'Hello\\; World!', _ChunkedValue.parse_rdata_text('"Hello; World!"')
        )
        # an unquoted, already backslash-escaped ; is valid RFC 1035
        # presentation format too (a bare \X escape), and is unambiguous
        self.assertEqual(
            'Hello\\;World!', _ChunkedValue.parse_rdata_text('Hello\\;World!')
        )
        # already escaped semi-colons are left alone, not double-escaped
        self.assertEqual(
            'Hello\\; World!',
            _ChunkedValue.parse_rdata_text('"Hello\\; World!"'),
        )
        # a *bare*, unescaped, unquoted ; is zone-file comment syntax and
        # truncates everything after it -- standard presentation-format
        # behavior, not something we work around
        self.assertEqual(
            'Hello', _ChunkedValue.parse_rdata_text('Hello;World!')
        )

        # multiple bare (unquoted) tokens, and mixes of quoted & unquoted
        # tokens, are simply concatenated -- this is standard RFC 1035
        # multi-character-string handling, not something we need to guess
        # about or reject
        self.assertEqual(
            'HelloWorld!', _ChunkedValue.parse_rdata_text('Hello World!')
        )
        self.assertEqual('quoted', _ChunkedValue.parse_rdata_text('"quo" ted'))

        # already-processed values pass straight through
        already = TxtValue('some.target.')
        self.assertIs(already, TxtValue.parse_rdata_text(already))

        # a literal backslash: escaped correctly on the way out, and
        # correctly unescaped (not doubled) on the way back in -- this used
        # to raise RrParseError (trailing backslash before a real closing
        # quote) or silently double the backslash (mid-string), depending
        # on position
        for content in ('a\\z', 'a\\', 'a\\\\z', 'a\\\\'):
            rdata = TxtValue(content).rdata_text
            self.assertEqual(content, _ChunkedValue.parse_rdata_text(rdata))

        # control characters round-trip via dnspython's \DDD decimal-octet
        # escapes -- previously not decoded at all (stored as literal
        # garbage), and not escaped on the way out (which would produce
        # invalid presentation text, e.g. dnspython itself refuses to parse
        # a raw embedded newline)
        for content in ('a\tb', 'a\nb', 'a\x00b', 'a\x7fb'):
            rdata = TxtValue(content).rdata_text
            self.assertEqual(content, _ChunkedValue.parse_rdata_text(rdata))

        # nothing but whitespace isn't valid presentation-format text
        with self.assertRaises(RrParseError):
            _ChunkedValue.parse_rdata_text('   ')

        # unterminated quoted string
        for value in ('"no closing quote', '"no closing \\" quote either'):
            with self.assertRaises(RrParseError):
                _ChunkedValue.parse_rdata_text(value)

        # a single character-string over the 255 byte RFC limit
        with self.assertRaises(RrParseError):
            _ChunkedValue.parse_rdata_text('"' + ('x' * 256) + '"')

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
        # chunk boundaries are computed on the raw/unmarked byte content
        # (matching the true RFC 255-byte-per-character-string limit), not
        # on octoDNS's marker-inflated internal string, so a \; marker
        # shifts the split point by one byte relative to counting the
        # marker's characters directly
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
            ('01234\\;56789', '"01234\\;56" "789"'),
            # escape before the boundary
            ('012345\\;6789', '"012345\\;6" "789"'),
            # escape after the boundary
            ('01234567\\;89', '"01234567" "\\;89"'),
            # escape spanning the boundary
            ('0123456\\;789', '"0123456\\;" "789"'),
            # multiple escapes at the boundary
            ('012345\\\\;6789', '"012345\\\\;" "6789"'),
            # exact size escape
            ('012345\\;', '"012345\\;"'),
            # spanning ending
            ('0123456\\;', '"0123456\\;"'),
            # a literal quote near the boundary
            ('0123456"89', '"0123456\\"" "89"'),
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

        # a missing (None) value is left as None rather than being coerced
        # into the literal string "None" -- reachable via lenient=True
        # construction of an already-invalid record
        self.assertEqual([None], TxtValue.process([None]))

        # a fully quoted string has its outer quotes removed
        self.assertEqual(['hello world'], TxtValue.process(['"hello world"']))

        # multiple quoted chunks are dechunked
        self.assertEqual(
            ['hello world'], TxtValue.process(['"hello" " world"'])
        )

        # a quoted string with escaped quotes inside it is properly
        # unescaped, not just naively stripped of its outer quotes
        self.assertEqual(
            ['has "embedded" quotes'],
            TxtValue.process(['"has \\"embedded\\" quotes"']),
        )

        # a quote not in the leading position isn't treated as quoted at
        # all, left completely as-is
        self.assertEqual(
            ['has a " in the middle'],
            TxtValue.process(['has a " in the middle']),
        )

        # quoted-looking input that doesn't actually parse (unterminated
        # quote) falls back to being used as-typed rather than raising --
        # process() is the lenient YAML path, validators are the real gate
        # for malformed data
        self.assertEqual(['"unterminated'], TxtValue.process(['"unterminated']))

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

    def test_rdata_text_escaping(self):
        # a literal backslash is escaped, matching real RFC 1035
        # presentation-format output (verified against dnspython) -- this
        # used to be left completely unescaped, which a real consumer would
        # misinterpret as escaping the following character
        self.assertEqual('"a\\\\b"', _ChunkedValue('a\\b').rdata_text)

        # control characters are escaped with \DDD decimal-octet escapes,
        # matching dnspython's own convention -- previously left raw, which
        # for a literal embedded newline dnspython itself refuses to parse
        # back (SyntaxError: newline in quoted string)
        self.assertEqual('"a\\009b"', _ChunkedValue('a\tb').rdata_text)
        self.assertEqual('"a\\010b"', _ChunkedValue('a\nb').rdata_text)
        self.assertEqual('"a\\000b"', _ChunkedValue('a\x00b').rdata_text)

        # a literal quote is still escaped as before
        self.assertEqual('"a\\"b"', _ChunkedValue('a"b').rdata_text)

        # an already-marked semi-colon renders as-is (still marked), not
        # bare and not double-escaped
        self.assertEqual('"a\\;b"', _ChunkedValue('a\\;b').rdata_text)
