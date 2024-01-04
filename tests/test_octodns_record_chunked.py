#
#
#

from unittest import TestCase

from octodns.record.chunked import _ChunkedValue
from octodns.record.spf import SpfRecord
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
