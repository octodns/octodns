#
#
#

from unittest import TestCase

from helpers import GeoProvider, SimpleProvider

from octodns.record import Record
from octodns.record.a import ARecord
from octodns.record.exception import ValidationError
from octodns.record.geo import GeoCodes, GeoValue
from octodns.zone import Zone


class TestRecordGeo(TestCase):
    zone = Zone('unit.tests.', [])

    def test_geo(self):
        geo_data = {
            'ttl': 42,
            'values': ['5.2.3.4', '6.2.3.4'],
            'geo': {
                'AF': ['1.1.1.1'],
                'AS-JP': ['2.2.2.2', '3.3.3.3'],
                'NA-US': ['4.4.4.4', '5.5.5.5'],
                'NA-US-CA': ['6.6.6.6', '7.7.7.7'],
            },
        }
        geo = ARecord(self.zone, 'geo', geo_data)
        self.assertEqual(geo_data, geo.data)

        other_data = {
            'ttl': 42,
            'values': ['5.2.3.4', '6.2.3.4'],
            'geo': {
                'AF': ['1.1.1.1'],
                'AS-JP': ['2.2.2.2', '3.3.3.3'],
                'NA-US': ['4.4.4.4', '5.5.5.5'],
                'NA-US-CA': ['6.6.6.6', '7.7.7.7'],
            },
        }
        other = ARecord(self.zone, 'geo', other_data)
        self.assertEqual(other_data, other.data)

        simple_target = SimpleProvider()
        geo_target = GeoProvider()

        # Geo provider doesn't consider identical geo to be changes
        self.assertFalse(geo.changes(geo, geo_target))

        # geo values don't impact equality
        other.geo['AF'].values = ['9.9.9.9']
        self.assertTrue(geo == other)
        # Non-geo supporting provider doesn't consider geo diffs to be changes
        self.assertFalse(geo.changes(other, simple_target))
        # Geo provider does consider geo diffs to be changes
        self.assertTrue(geo.changes(other, geo_target))

        # Object without geo doesn't impact equality
        other.geo = {}
        self.assertTrue(geo == other)
        # Non-geo supporting provider doesn't consider lack of geo a diff
        self.assertFalse(geo.changes(other, simple_target))
        # Geo provider does consider lack of geo diffs to be changes
        self.assertTrue(geo.changes(other, geo_target))

        # __repr__ doesn't blow up
        geo.__repr__()


class TestRecordGeoCodes(TestCase):
    zone = Zone('unit.tests.', [])

    def test_validate(self):
        prefix = 'xyz '

        # All valid
        self.assertEqual([], GeoCodes.validate('NA', prefix))
        self.assertEqual([], GeoCodes.validate('NA-US', prefix))
        self.assertEqual([], GeoCodes.validate('NA-US-OR', prefix))

        # Just plain bad
        self.assertEqual(
            ['xyz invalid geo code "XX-YY-ZZ-AA"'],
            GeoCodes.validate('XX-YY-ZZ-AA', prefix),
        )
        self.assertEqual(
            ['xyz unknown continent code "X-Y-Z"'],
            GeoCodes.validate('X-Y-Z', prefix),
        )
        self.assertEqual(
            ['xyz unknown continent code "XXX-Y-Z"'],
            GeoCodes.validate('XXX-Y-Z', prefix),
        )

        # Bad continent
        self.assertEqual(
            ['xyz unknown continent code "XX"'], GeoCodes.validate('XX', prefix)
        )
        # Bad continent good country
        self.assertEqual(
            ['xyz unknown continent code "XX-US"'],
            GeoCodes.validate('XX-US', prefix),
        )
        # Bad continent good country and province
        self.assertEqual(
            ['xyz unknown continent code "XX-US-OR"'],
            GeoCodes.validate('XX-US-OR', prefix),
        )

        # Bad country, good continent
        self.assertEqual(
            ['xyz unknown country code "NA-XX"'],
            GeoCodes.validate('NA-XX', prefix),
        )
        # Bad country, good continent and state
        self.assertEqual(
            ['xyz unknown country code "NA-XX-OR"'],
            GeoCodes.validate('NA-XX-OR', prefix),
        )
        # Good country, good continent, but bad match
        self.assertEqual(
            ['xyz unknown country code "NA-GB"'],
            GeoCodes.validate('NA-GB', prefix),
        )

        # Bad province code, good continent and country
        self.assertEqual(
            ['xyz unknown province code "NA-US-XX"'],
            GeoCodes.validate('NA-US-XX', prefix),
        )

    def test_parse(self):
        self.assertEqual(
            {
                'continent_code': 'NA',
                'country_code': None,
                'province_code': None,
            },
            GeoCodes.parse('NA'),
        )
        self.assertEqual(
            {
                'continent_code': 'NA',
                'country_code': 'US',
                'province_code': None,
            },
            GeoCodes.parse('NA-US'),
        )
        self.assertEqual(
            {
                'continent_code': 'NA',
                'country_code': 'US',
                'province_code': 'CA',
            },
            GeoCodes.parse('NA-US-CA'),
        )

    def test_country_to_code(self):
        self.assertEqual('NA-US', GeoCodes.country_to_code('US'))
        self.assertEqual('EU-GB', GeoCodes.country_to_code('GB'))
        self.assertFalse(GeoCodes.country_to_code('XX'))

    def test_province_to_code(self):
        self.assertEqual('NA-US-OR', GeoCodes.province_to_code('OR'))
        self.assertEqual('NA-US-KY', GeoCodes.province_to_code('KY'))
        self.assertEqual('NA-CA-AB', GeoCodes.province_to_code('AB'))
        self.assertEqual('NA-CA-BC', GeoCodes.province_to_code('BC'))
        self.assertFalse(GeoCodes.province_to_code('XX'))

    def test_geo_value(self):
        code = 'NA-US-CA'
        values = ['1.2.3.4']
        geo = GeoValue(code, values)
        self.assertEqual(code, geo.code)
        self.assertEqual('NA', geo.continent_code)
        self.assertEqual('US', geo.country_code)
        self.assertEqual('CA', geo.subdivision_code)
        self.assertEqual(values, geo.values)
        self.assertEqual(['NA-US', 'NA'], list(geo.parents))

        a = GeoValue('NA-US-CA', values)
        b = GeoValue('AP-JP', values)
        c = GeoValue('NA-US-CA', ['2.3.4.5'])

        self.assertEqual(a, a)
        self.assertEqual(b, b)
        self.assertEqual(c, c)

        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(b, a)
        self.assertNotEqual(b, c)
        self.assertNotEqual(c, a)
        self.assertNotEqual(c, b)

        self.assertTrue(a > b)
        self.assertTrue(a < c)
        self.assertTrue(b < a)
        self.assertTrue(b < c)
        self.assertTrue(c > a)
        self.assertTrue(c > b)

        self.assertTrue(a >= a)
        self.assertTrue(a >= b)
        self.assertTrue(a <= c)
        self.assertTrue(b <= a)
        self.assertTrue(b <= b)
        self.assertTrue(b <= c)
        self.assertTrue(c > a)
        self.assertTrue(c > b)
        self.assertTrue(c >= b)

    def test_validation(self):
        # invalid ip address
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'geo': {'NA': ['hello'], 'NA-US': ['1.2.3.5', '1.2.3.6']},
                    'type': 'A',
                    'ttl': 600,
                    'value': '1.2.3.4',
                },
            )
        self.assertEqual(
            ['invalid IPv4 address "hello"'], ctx.exception.reasons
        )

        # invalid geo code
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'geo': {'XYZ': ['1.2.3.4']},
                    'type': 'A',
                    'ttl': 600,
                    'value': '1.2.3.4',
                },
            )
        self.assertEqual(['invalid geo "XYZ"'], ctx.exception.reasons)

        # invalid ip address
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'geo': {'NA': ['hello'], 'NA-US': ['1.2.3.5', 'goodbye']},
                    'type': 'A',
                    'ttl': 600,
                    'value': '1.2.3.4',
                },
            )
        self.assertEqual(
            ['invalid IPv4 address "hello"', 'invalid IPv4 address "goodbye"'],
            ctx.exception.reasons,
        )

        # invalid healthcheck protocol
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'a',
                {
                    'geo': {'NA': ['1.2.3.5'], 'NA-US': ['1.2.3.5', '1.2.3.6']},
                    'type': 'A',
                    'ttl': 600,
                    'value': '1.2.3.4',
                    'octodns': {'healthcheck': {'protocol': 'FTP'}},
                },
            )
        self.assertEqual(
            ['invalid healthcheck protocol'], ctx.exception.reasons
        )
