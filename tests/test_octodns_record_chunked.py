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

    def test_large_values(self):
        # There is additional testing in TXT

        # "standard" format quoted and split value
        value = (
            '"Lorem ipsum dolor sit amet, consectetur '
            'adipiscing elit, sed do eiusmod tempor incididunt ut '
            'labore et dolore magna aliqua. Ut enim ad minim veniam, '
            'quis nostrud exercitation ullamco laboris nisi ut aliquip '
            'ex" " ea commodo consequat. Duis aute irure dolor in '
            'reprehenderit in voluptate velit esse cillum dolore eu '
            'fugiat nulla pariatur. Excepteur sint occaecat cupidatat '
            'non proident, sunt in culpa qui officia deserunt mollit '
            'anim id est laborum."'
        )
        chunked = _ChunkedValue.process([value])
        self.assertEqual(1, len(chunked))
        chunked = chunked[0]
        self.assertIsInstance(chunked, _ChunkedValue)
        dechunked_value = (
            'Lorem ipsum dolor sit amet, consectetur '
            'adipiscing elit, sed do eiusmod tempor incididunt ut '
            'labore et dolore magna aliqua. Ut enim ad minim veniam, '
            'quis nostrud exercitation ullamco laboris nisi ut aliquip '
            'ex ea commodo consequat. Duis aute irure dolor in '
            'reprehenderit in voluptate velit esse cillum dolore eu '
            'fugiat nulla pariatur. Excepteur sint occaecat cupidatat '
            'non proident, sunt in culpa qui officia deserunt mollit '
            'anim id est laborum.'
        )
        self.assertEqual(dechunked_value, chunked)

        # already dechunked, noop
        chunked = _ChunkedValue.process([dechunked_value])[0]
        self.assertEqual(dechunked_value, chunked)

        # leading whitespace
        chunked = _ChunkedValue.process([f' {value}'])[0]
        self.assertEqual(dechunked_value, chunked)
        chunked = _ChunkedValue.process([f'  {value}'])[0]
        self.assertEqual(dechunked_value, chunked)
        chunked = _ChunkedValue.process([f'\t{value}'])[0]
        self.assertEqual(dechunked_value, chunked)
        chunked = _ChunkedValue.process([f'\t\t{value}'])[0]
        self.assertEqual(dechunked_value, chunked)
        chunked = _ChunkedValue.process([f' \t{value}'])[0]
        self.assertEqual(dechunked_value, chunked)

        # trailing whitespace
        chunked = _ChunkedValue.process([f'{value} '])[0]
        self.assertEqual(dechunked_value, chunked)
        chunked = _ChunkedValue.process([f'{value}  '])[0]
        self.assertEqual(dechunked_value, chunked)
        chunked = _ChunkedValue.process([f'{value}\t'])[0]
        self.assertEqual(dechunked_value, chunked)
        chunked = _ChunkedValue.process([f'{value}\t\t'])[0]
        self.assertEqual(dechunked_value, chunked)
        chunked = _ChunkedValue.process([f'{value} \t'])[0]
        self.assertEqual(dechunked_value, chunked)

        # both
        chunked = _ChunkedValue.process([f' {value} '])[0]
        self.assertEqual(dechunked_value, chunked)
        chunked = _ChunkedValue.process([f'\t{value}  '])[0]
        self.assertEqual(dechunked_value, chunked)
        chunked = _ChunkedValue.process([f' {value}\t'])[0]
        self.assertEqual(dechunked_value, chunked)

        # variations of whitepsace in the chunk seperator
        multi = value.replace('" "', '"  "')
        chunked = _ChunkedValue.process([multi])[0]
        self.assertEqual(dechunked_value, chunked)
        multi = value.replace('" "', '"\t"')
        chunked = _ChunkedValue.process([multi])[0]
        self.assertEqual(dechunked_value, chunked)
        multi = value.replace('" "', '"\t\t"')
        chunked = _ChunkedValue.process([multi])[0]
        self.assertEqual(dechunked_value, chunked)
        multi = value.replace('" "', '" \t"')
        chunked = _ChunkedValue.process([multi])[0]
        self.assertEqual(dechunked_value, chunked)

        # ~real world test case
        values = [
            'before',
            ' "v=DKIM1\\; h=sha256\\; k=rsa\\; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAx78E7PtJvr8vpoNgHdIAe+llFKoy8WuTXDd6Z5mm3D4AUva9MBt5fFetxg/kcRy3KMDnMw6kDybwbpS/oPw1ylk6DL1xit7Cr5xeYYSWKukxXURAlHwT2K72oUsFKRUvN1X9lVysAeo+H8H/22Z9fJ0P30sOuRIRqCaiz+OiUYicxy4x"   "rpfH2s9a+o3yRwX3zhlp8GjRmmmyK5mf7CkQTCfjnKVsYtB7mabXXmClH9tlcymnBMoN9PeXxaS5JRRysVV8RBCC9/wmfp9y//cck8nvE/MavFpSUHvv+TfTTdVKDlsXPjKX8iZQv0nO3xhspgkqFquKjydiR8nf4meHhwIDAQAB"  ',
            'z after',
        ]
        chunked = _ChunkedValue.process(values)
        expected = [
            'before',
            'v=DKIM1\\; h=sha256\\; k=rsa\\; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAx78E7PtJvr8vpoNgHdIAe+llFKoy8WuTXDd6Z5mm3D4AUva9MBt5fFetxg/kcRy3KMDnMw6kDybwbpS/oPw1ylk6DL1xit7Cr5xeYYSWKukxXURAlHwT2K72oUsFKRUvN1X9lVysAeo+H8H/22Z9fJ0P30sOuRIRqCaiz+OiUYicxy4xrpfH2s9a+o3yRwX3zhlp8GjRmmmyK5mf7CkQTCfjnKVsYtB7mabXXmClH9tlcymnBMoN9PeXxaS5JRRysVV8RBCC9/wmfp9y//cck8nvE/MavFpSUHvv+TfTTdVKDlsXPjKX8iZQv0nO3xhspgkqFquKjydiR8nf4meHhwIDAQAB',
            'z after',
        ]
        self.assertEqual(expected, chunked)
