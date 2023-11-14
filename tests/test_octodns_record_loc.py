#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.loc import LocRecord, LocValue
from octodns.record.rr import RrParseError
from octodns.zone import Zone


class TestRecordLoc(TestCase):
    zone = Zone('unit.tests.', [])

    def test_loc(self):
        a_values = [
            LocValue(
                {
                    'lat_degrees': 31,
                    'lat_minutes': 58,
                    'lat_seconds': 52.1,
                    'lat_direction': 'S',
                    'long_degrees': 115,
                    'long_minutes': 49,
                    'long_seconds': 11.7,
                    'long_direction': 'E',
                    'altitude': 20,
                    'size': 10,
                    'precision_horz': 10,
                    'precision_vert': 2,
                }
            )
        ]
        a_data = {'ttl': 30, 'values': a_values}
        a = LocRecord(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values[0]['lat_degrees'], a.values[0].lat_degrees)
        self.assertEqual(a_values[0]['lat_minutes'], a.values[0].lat_minutes)
        self.assertEqual(a_values[0]['lat_seconds'], a.values[0].lat_seconds)
        self.assertEqual(
            a_values[0]['lat_direction'], a.values[0].lat_direction
        )
        self.assertEqual(a_values[0]['long_degrees'], a.values[0].long_degrees)
        self.assertEqual(a_values[0]['long_minutes'], a.values[0].long_minutes)
        self.assertEqual(a_values[0]['long_seconds'], a.values[0].long_seconds)
        self.assertEqual(
            a_values[0]['long_direction'], a.values[0].long_direction
        )
        self.assertEqual(a_values[0]['altitude'], a.values[0].altitude)
        self.assertEqual(a_values[0]['size'], a.values[0].size)
        self.assertEqual(
            a_values[0]['precision_horz'], a.values[0].precision_horz
        )
        self.assertEqual(
            a_values[0]['precision_vert'], a.values[0].precision_vert
        )

        b_value = LocValue(
            {
                'lat_degrees': 32,
                'lat_minutes': 7,
                'lat_seconds': 19,
                'lat_direction': 'S',
                'long_degrees': 116,
                'long_minutes': 2,
                'long_seconds': 25,
                'long_direction': 'E',
                'altitude': 10,
                'size': 1,
                'precision_horz': 10000,
                'precision_vert': 10,
            }
        )
        b_data = {'ttl': 30, 'value': b_value}
        b = LocRecord(self.zone, 'b', b_data)
        self.assertEqual(b_value['lat_degrees'], b.values[0].lat_degrees)
        self.assertEqual(b_value['lat_minutes'], b.values[0].lat_minutes)
        self.assertEqual(b_value['lat_seconds'], b.values[0].lat_seconds)
        self.assertEqual(b_value['lat_direction'], b.values[0].lat_direction)
        self.assertEqual(b_value['long_degrees'], b.values[0].long_degrees)
        self.assertEqual(b_value['long_minutes'], b.values[0].long_minutes)
        self.assertEqual(b_value['long_seconds'], b.values[0].long_seconds)
        self.assertEqual(b_value['long_direction'], b.values[0].long_direction)
        self.assertEqual(b_value['altitude'], b.values[0].altitude)
        self.assertEqual(b_value['size'], b.values[0].size)
        self.assertEqual(b_value['precision_horz'], b.values[0].precision_horz)
        self.assertEqual(b_value['precision_vert'], b.values[0].precision_vert)
        self.assertEqual(b_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in lat_direction causes change
        other = LocRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].lat_direction = 'N'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in altitude causes change
        other.values[0].altitude = a.values[0].altitude
        other.values[0].altitude = -10
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_loc_value_rdata_text(self):
        # only the exact correct number of words is allowed
        for i in tuple(range(0, 12)) + (13,):
            s = ''.join(['word'] * i)
            with self.assertRaises(RrParseError):
                LocValue.parse_rdata_text(s)

        # type conversions are best effort
        self.assertEqual(
            {
                'altitude': 'six',
                'lat_degrees': 'zero',
                'lat_direction': 'S',
                'lat_minutes': 'one',
                'lat_seconds': 'two',
                'long_degrees': 'three',
                'long_direction': 'W',
                'long_minutes': 'four',
                'long_seconds': 'five',
                'precision_horz': 'eight',
                'precision_vert': 'nine',
                'size': 'seven',
            },
            LocValue.parse_rdata_text(
                'zero one two S three four five W six seven eight nine'
            ),
        )

        # valid
        s = '0 1 2.2 N 3 4 5.5 E 6.6m 7.7m 8.8m 9.9m'
        self.assertEqual(
            {
                'altitude': 6.6,
                'lat_degrees': 0,
                'lat_direction': 'N',
                'lat_minutes': 1,
                'lat_seconds': 2.2,
                'long_degrees': 3,
                'long_direction': 'E',
                'long_minutes': 4,
                'long_seconds': 5.5,
                'precision_horz': 8.8,
                'precision_vert': 9.9,
                'size': 7.7,
            },
            LocValue.parse_rdata_text(s),
        )

        # quoted
        s = '0 1 2.2 "N" 3 4 5.5 "E" "6.6m" "7.7m" "8.8m" "9.9m"'
        self.assertEqual(
            {
                'altitude': 6.6,
                'lat_degrees': 0,
                'lat_direction': 'N',
                'lat_minutes': 1,
                'lat_seconds': 2.2,
                'long_degrees': 3,
                'long_direction': 'E',
                'long_minutes': 4,
                'long_seconds': 5.5,
                'precision_horz': 8.8,
                'precision_vert': 9.9,
                'size': 7.7,
            },
            LocValue.parse_rdata_text(s),
        )

        # make sure that the cstor is using parse_rdata_text
        zone = Zone('unit.tests.', [])
        a = LocRecord(
            zone,
            'mx',
            {
                'type': 'LOC',
                'ttl': 42,
                'value': {
                    'altitude': 6.6,
                    'lat_degrees': 0,
                    'lat_direction': 'N',
                    'lat_minutes': 1,
                    'lat_seconds': 2.2,
                    'long_degrees': 3,
                    'long_direction': 'E',
                    'long_minutes': 4,
                    'long_seconds': 5.5,
                    'precision_horz': 8.8,
                    'precision_vert': 9.9,
                    'size': 7.7,
                },
            },
        )
        self.assertEqual(0, a.values[0].lat_degrees)
        self.assertEqual(1, a.values[0].lat_minutes)
        self.assertEqual(2.2, a.values[0].lat_seconds)
        self.assertEqual('N', a.values[0].lat_direction)
        self.assertEqual(3, a.values[0].long_degrees)
        self.assertEqual(4, a.values[0].long_minutes)
        self.assertEqual(5.5, a.values[0].long_seconds)
        self.assertEqual('E', a.values[0].long_direction)
        self.assertEqual(6.6, a.values[0].altitude)
        self.assertEqual(7.7, a.values[0].size)
        self.assertEqual(8.8, a.values[0].precision_horz)
        self.assertEqual(9.9, a.values[0].precision_vert)
        self.assertEqual(s.replace('"', ''), a.values[0].rdata_text)

    def test_loc_value(self):
        a = LocValue(
            {
                'lat_degrees': 31,
                'lat_minutes': 58,
                'lat_seconds': 52.1,
                'lat_direction': 'S',
                'long_degrees': 115,
                'long_minutes': 49,
                'long_seconds': 11.7,
                'long_direction': 'E',
                'altitude': 20,
                'size': 10,
                'precision_horz': 10,
                'precision_vert': 2,
            }
        )
        b = LocValue(
            {
                'lat_degrees': 32,
                'lat_minutes': 7,
                'lat_seconds': 19,
                'lat_direction': 'S',
                'long_degrees': 116,
                'long_minutes': 2,
                'long_seconds': 25,
                'long_direction': 'E',
                'altitude': 10,
                'size': 1,
                'precision_horz': 10000,
                'precision_vert': 10,
            }
        )
        c = LocValue(
            {
                'lat_degrees': 53,
                'lat_minutes': 14,
                'lat_seconds': 10,
                'lat_direction': 'N',
                'long_degrees': 2,
                'long_minutes': 18,
                'long_seconds': 26,
                'long_direction': 'W',
                'altitude': 10,
                'size': 1,
                'precision_horz': 1000,
                'precision_vert': 10,
            }
        )

        self.assertEqual(a, a)
        self.assertEqual(b, b)
        self.assertEqual(c, c)

        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(b, a)
        self.assertNotEqual(b, c)
        self.assertNotEqual(c, a)
        self.assertNotEqual(c, b)

        self.assertTrue(a < b)
        self.assertTrue(a < c)

        self.assertTrue(b > a)
        self.assertTrue(b < c)

        self.assertTrue(c > a)
        self.assertTrue(c > b)

        self.assertTrue(a <= b)
        self.assertTrue(a <= c)
        self.assertTrue(a <= a)
        self.assertTrue(a >= a)

        self.assertTrue(b >= a)
        self.assertTrue(b <= c)
        self.assertTrue(b >= b)
        self.assertTrue(b <= b)

        self.assertTrue(c >= a)
        self.assertTrue(c >= b)
        self.assertTrue(c >= c)
        self.assertTrue(c <= c)

        self.assertEqual(31, a.lat_degrees)
        a.lat_degrees = a.lat_degrees + 1
        self.assertEqual(32, a.lat_degrees)

        self.assertEqual(58, a.lat_minutes)
        a.lat_minutes = a.lat_minutes + 1
        self.assertEqual(59, a.lat_minutes)

        self.assertEqual(52.1, a.lat_seconds)
        a.lat_seconds = a.lat_seconds + 1
        self.assertEqual(53.1, a.lat_seconds)

        self.assertEqual('S', a.lat_direction)
        a.lat_direction = 'N'
        self.assertEqual('N', a.lat_direction)

        self.assertEqual(115, a.long_degrees)
        a.long_degrees = a.long_degrees + 1
        self.assertEqual(116, a.long_degrees)

        self.assertEqual(49, a.long_minutes)
        a.long_minutes = a.long_minutes + 1
        self.assertEqual(50, a.long_minutes)

        self.assertEqual(11.7, a.long_seconds)
        a.long_seconds = a.long_seconds + 1
        self.assertEqual(12.7, a.long_seconds)

        self.assertEqual('E', a.long_direction)
        a.long_direction = 'W'
        self.assertEqual('W', a.long_direction)

        self.assertEqual(20, a.altitude)
        a.altitude = a.altitude + 1
        self.assertEqual(21, a.altitude)

        self.assertEqual(10, a.size)
        a.size = a.size + 1
        self.assertEqual(11, a.size)

        self.assertEqual(10, a.precision_horz)
        a.precision_horz = a.precision_horz + 1
        self.assertEqual(11, a.precision_horz)

        self.assertEqual(2, a.precision_vert)
        a.precision_vert = a.precision_vert + 1
        self.assertEqual(3, a.precision_vert)

        # Hash
        values = set()
        values.add(a)
        self.assertTrue(a in values)
        self.assertFalse(b in values)
        values.add(b)
        self.assertTrue(b in values)

    def test_validation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            '',
            {
                'type': 'LOC',
                'ttl': 600,
                'value': {
                    'lat_degrees': 31,
                    'lat_minutes': 58,
                    'lat_seconds': 52.1,
                    'lat_direction': 'S',
                    'long_degrees': 115,
                    'long_minutes': 49,
                    'long_seconds': 11.7,
                    'long_direction': 'E',
                    'altitude': 20,
                    'size': 10,
                    'precision_horz': 10,
                    'precision_vert': 2,
                },
            },
        )

        # missing int key
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'LOC',
                    'ttl': 600,
                    'value': {
                        'lat_minutes': 58,
                        'lat_seconds': 52.1,
                        'lat_direction': 'S',
                        'long_degrees': 115,
                        'long_minutes': 49,
                        'long_seconds': 11.7,
                        'long_direction': 'E',
                        'altitude': 20,
                        'size': 10,
                        'precision_horz': 10,
                        'precision_vert': 2,
                    },
                },
            )

        self.assertEqual(['missing lat_degrees'], ctx.exception.reasons)

        # missing float key
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'LOC',
                    'ttl': 600,
                    'value': {
                        'lat_degrees': 31,
                        'lat_minutes': 58,
                        'lat_direction': 'S',
                        'long_degrees': 115,
                        'long_minutes': 49,
                        'long_seconds': 11.7,
                        'long_direction': 'E',
                        'altitude': 20,
                        'size': 10,
                        'precision_horz': 10,
                        'precision_vert': 2,
                    },
                },
            )

        self.assertEqual(['missing lat_seconds'], ctx.exception.reasons)

        # missing text key
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'LOC',
                    'ttl': 600,
                    'value': {
                        'lat_degrees': 31,
                        'lat_minutes': 58,
                        'lat_seconds': 52.1,
                        'long_degrees': 115,
                        'long_minutes': 49,
                        'long_seconds': 11.7,
                        'long_direction': 'E',
                        'altitude': 20,
                        'size': 10,
                        'precision_horz': 10,
                        'precision_vert': 2,
                    },
                },
            )

        self.assertEqual(['missing lat_direction'], ctx.exception.reasons)

        # invalid direction
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'LOC',
                    'ttl': 600,
                    'value': {
                        'lat_degrees': 31,
                        'lat_minutes': 58,
                        'lat_seconds': 52.1,
                        'lat_direction': 'U',
                        'long_degrees': 115,
                        'long_minutes': 49,
                        'long_seconds': 11.7,
                        'long_direction': 'E',
                        'altitude': 20,
                        'size': 10,
                        'precision_horz': 10,
                        'precision_vert': 2,
                    },
                },
            )

        self.assertEqual(
            ['invalid direction for lat_direction "U"'], ctx.exception.reasons
        )

        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'LOC',
                    'ttl': 600,
                    'value': {
                        'lat_degrees': 31,
                        'lat_minutes': 58,
                        'lat_seconds': 52.1,
                        'lat_direction': 'S',
                        'long_degrees': 115,
                        'long_minutes': 49,
                        'long_seconds': 11.7,
                        'long_direction': 'N',
                        'altitude': 20,
                        'size': 10,
                        'precision_horz': 10,
                        'precision_vert': 2,
                    },
                },
            )

        self.assertEqual(
            ['invalid direction for long_direction "N"'], ctx.exception.reasons
        )

        # invalid degrees
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'LOC',
                    'ttl': 600,
                    'value': {
                        'lat_degrees': 360,
                        'lat_minutes': 58,
                        'lat_seconds': 52.1,
                        'lat_direction': 'S',
                        'long_degrees': 115,
                        'long_minutes': 49,
                        'long_seconds': 11.7,
                        'long_direction': 'E',
                        'altitude': 20,
                        'size': 10,
                        'precision_horz': 10,
                        'precision_vert': 2,
                    },
                },
            )

        self.assertEqual(
            ['invalid value for lat_degrees "360"'], ctx.exception.reasons
        )

        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'LOC',
                    'ttl': 600,
                    'value': {
                        'lat_degrees': 'nope',
                        'lat_minutes': 58,
                        'lat_seconds': 52.1,
                        'lat_direction': 'S',
                        'long_degrees': 115,
                        'long_minutes': 49,
                        'long_seconds': 11.7,
                        'long_direction': 'E',
                        'altitude': 20,
                        'size': 10,
                        'precision_horz': 10,
                        'precision_vert': 2,
                    },
                },
            )

        self.assertEqual(['invalid lat_degrees "nope"'], ctx.exception.reasons)

        # invalid minutes
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'LOC',
                    'ttl': 600,
                    'value': {
                        'lat_degrees': 31,
                        'lat_minutes': 60,
                        'lat_seconds': 52.1,
                        'lat_direction': 'S',
                        'long_degrees': 115,
                        'long_minutes': 49,
                        'long_seconds': 11.7,
                        'long_direction': 'E',
                        'altitude': 20,
                        'size': 10,
                        'precision_horz': 10,
                        'precision_vert': 2,
                    },
                },
            )

        self.assertEqual(
            ['invalid value for lat_minutes "60"'], ctx.exception.reasons
        )

        # invalid seconds
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'LOC',
                    'ttl': 600,
                    'value': {
                        'lat_degrees': 31,
                        'lat_minutes': 58,
                        'lat_seconds': 60,
                        'lat_direction': 'S',
                        'long_degrees': 115,
                        'long_minutes': 49,
                        'long_seconds': 11.7,
                        'long_direction': 'E',
                        'altitude': 20,
                        'size': 10,
                        'precision_horz': 10,
                        'precision_vert': 2,
                    },
                },
            )

        self.assertEqual(
            ['invalid value for lat_seconds "60"'], ctx.exception.reasons
        )

        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'LOC',
                    'ttl': 600,
                    'value': {
                        'lat_degrees': 31,
                        'lat_minutes': 58,
                        'lat_seconds': 'nope',
                        'lat_direction': 'S',
                        'long_degrees': 115,
                        'long_minutes': 49,
                        'long_seconds': 11.7,
                        'long_direction': 'E',
                        'altitude': 20,
                        'size': 10,
                        'precision_horz': 10,
                        'precision_vert': 2,
                    },
                },
            )

        self.assertEqual(['invalid lat_seconds "nope"'], ctx.exception.reasons)

        # invalid altitude
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'LOC',
                    'ttl': 600,
                    'value': {
                        'lat_degrees': 31,
                        'lat_minutes': 58,
                        'lat_seconds': 52.1,
                        'lat_direction': 'S',
                        'long_degrees': 115,
                        'long_minutes': 49,
                        'long_seconds': 11.7,
                        'long_direction': 'E',
                        'altitude': -666666,
                        'size': 10,
                        'precision_horz': 10,
                        'precision_vert': 2,
                    },
                },
            )

        self.assertEqual(
            ['invalid value for altitude "-666666"'], ctx.exception.reasons
        )

        # invalid size
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'LOC',
                    'ttl': 600,
                    'value': {
                        'lat_degrees': 31,
                        'lat_minutes': 58,
                        'lat_seconds': 52.1,
                        'lat_direction': 'S',
                        'long_degrees': 115,
                        'long_minutes': 49,
                        'long_seconds': 11.7,
                        'long_direction': 'E',
                        'altitude': 20,
                        'size': 99999999.99,
                        'precision_horz': 10,
                        'precision_vert': 2,
                    },
                },
            )

        self.assertEqual(
            ['invalid value for size "99999999.99"'], ctx.exception.reasons
        )
