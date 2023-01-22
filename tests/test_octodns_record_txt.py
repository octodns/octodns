#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.txt import TxtRecord
from octodns.zone import Zone


class TestRecordTxt(TestCase):
    zone = Zone('unit.tests.', [])

    def assertMultipleValues(self, _type, a_values, b_value):
        a_data = {'ttl': 30, 'values': a_values}
        a = _type(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values, a.values)
        self.assertEqual(a_data, a.data)

        b_data = {'ttl': 30, 'value': b_value}
        b = _type(self.zone, 'b', b_data)
        self.assertEqual([b_value], b.values)
        self.assertEqual(b_data, b.data)

    def test_txt(self):
        a_values = ['a one', 'a two']
        b_value = 'b other'
        self.assertMultipleValues(TxtRecord, a_values, b_value)

    def test_validation(self):
        # doesn't blow up (name & zone here don't make any sense, but not
        # important)
        Record.new(
            self.zone,
            '',
            {
                'type': 'TXT',
                'ttl': 600,
                'values': [
                    'hello world',
                    'this has some\\; semi-colons\\; in it',
                ],
            },
        )

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'TXT', 'ttl': 600})
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing escapes
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 600,
                    'value': 'this has some; semi-colons\\; in it',
                },
            )
        self.assertEqual(
            ['unescaped ; in "this has some; semi-colons\\; in it"'],
            ctx.exception.reasons,
        )

    def test_long_value_chunking(self):
        expected = (
            '"Lorem ipsum dolor sit amet, consectetur adipiscing '
            'elit, sed do eiusmod tempor incididunt ut labore et dolore '
            'magna aliqua. Ut enim ad minim veniam, quis nostrud '
            'exercitation ullamco laboris nisi ut aliquip ex ea commodo '
            'consequat. Duis aute irure dolor i" "n reprehenderit in '
            'voluptate velit esse cillum dolore eu fugiat nulla pariatur. '
            'Excepteur sint occaecat cupidatat non proident, sunt in culpa '
            'qui officia deserunt mollit anim id est laborum."'
        )

        long_value = (
            'Lorem ipsum dolor sit amet, consectetur adipiscing '
            'elit, sed do eiusmod tempor incididunt ut labore et dolore '
            'magna aliqua. Ut enim ad minim veniam, quis nostrud '
            'exercitation ullamco laboris nisi ut aliquip ex ea commodo '
            'consequat. Duis aute irure dolor in reprehenderit in '
            'voluptate velit esse cillum dolore eu fugiat nulla '
            'pariatur. Excepteur sint occaecat cupidatat non proident, '
            'sunt in culpa qui officia deserunt mollit anim id est '
            'laborum.'
        )
        # Single string
        single = Record.new(
            self.zone,
            '',
            {
                'type': 'TXT',
                'ttl': 600,
                'values': [
                    'hello world',
                    long_value,
                    'this has some\\; semi-colons\\; in it',
                ],
            },
        )
        self.assertEqual(3, len(single.values))
        self.assertEqual(3, len(single.chunked_values))
        # Note we are checking that this normalizes the chunking, not that we
        # get out what we put in.
        self.assertEqual(expected, single.chunked_values[0])

        long_split_value = (
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
        # Chunked
        chunked = Record.new(
            self.zone,
            '',
            {
                'type': 'TXT',
                'ttl': 600,
                'values': [
                    '"hello world"',
                    long_split_value,
                    '"this has some\\; semi-colons\\; in it"',
                ],
            },
        )
        self.assertEqual(expected, chunked.chunked_values[0])
        # should be single values, no quoting
        self.assertEqual(single.values, chunked.values)
        # should be chunked values, with quoting
        self.assertEqual(single.chunked_values, chunked.chunked_values)
