#
#
#

from unittest import TestCase

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


class TestChunkedValue(TestCase):
    def test_validate(self):
        # valid stuff
        for data in ('a', 'ab', 'abcdefg', 'abc def', 'abc\\; def'):
            self.assertFalse(_ChunkedValue.validate(data, 'TXT'))
            self.assertFalse(_ChunkedValue.validate([data], 'TXT'))

        # missing
        for data in (None, []):
            self.assertEqual(
                ['missing value(s)'], _ChunkedValue.validate(data, 'TXT')
            )

        # unescaped ;
        self.assertEqual(
            ['unescaped ; in "hello; world"'],
            _ChunkedValue.validate('hello; world', 'TXT'),
        )

        # non-asci
        self.assertEqual(
            ['non ASCII character in "v=spf1 –all"'],
            _ChunkedValue.validate('v=spf1 –all', 'TXT'),
        )
        self.assertEqual(
            ['non ASCII character in "Déjà vu"'],
            _ChunkedValue.validate('Déjà vu', 'TXT'),
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
