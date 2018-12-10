#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from octodns.record.geo import GeoCodes


class TestRecordGeoCodes(TestCase):

    def test_validate(self):
        prefix = 'xyz '

        # All valid
        self.assertEquals([], GeoCodes.validate('NA', prefix))
        self.assertEquals([], GeoCodes.validate('NA-US', prefix))
        self.assertEquals([], GeoCodes.validate('NA-US-OR', prefix))

        # Just plain bad
        self.assertEquals(['xyz invalid geo code "XX-YY-ZZ-AA"'],
                          GeoCodes.validate('XX-YY-ZZ-AA', prefix))
        self.assertEquals(['xyz unknown continent code "X-Y-Z"'],
                          GeoCodes.validate('X-Y-Z', prefix))
        self.assertEquals(['xyz unknown continent code "XXX-Y-Z"'],
                          GeoCodes.validate('XXX-Y-Z', prefix))

        # Bad continent
        self.assertEquals(['xyz unknown continent code "XX"'],
                          GeoCodes.validate('XX', prefix))
        # Bad continent good country
        self.assertEquals(['xyz unknown continent code "XX-US"'],
                          GeoCodes.validate('XX-US', prefix))
        # Bad continent good country and province
        self.assertEquals(['xyz unknown continent code "XX-US-OR"'],
                          GeoCodes.validate('XX-US-OR', prefix))

        # Bad country, good continent
        self.assertEquals(['xyz unknown country code "NA-XX"'],
                          GeoCodes.validate('NA-XX', prefix))
        # Bad country, good continent and state
        self.assertEquals(['xyz unknown country code "NA-XX-OR"'],
                          GeoCodes.validate('NA-XX-OR', prefix))
        # Good country, good continent, but bad match
        self.assertEquals(['xyz unknown country code "NA-GB"'],
                          GeoCodes.validate('NA-GB', prefix))

        # Bad province code, good continent and country
        self.assertEquals(['xyz unknown province code "NA-US-XX"'],
                          GeoCodes.validate('NA-US-XX', prefix))

    def test_parse(self):
        self.assertEquals({
            'continent_code': 'NA',
            'country_code': None,
            'province_code': None,
        }, GeoCodes.parse('NA'))
        self.assertEquals({
            'continent_code': 'NA',
            'country_code': 'US',
            'province_code': None,
        }, GeoCodes.parse('NA-US'))
        self.assertEquals({
            'continent_code': 'NA',
            'country_code': 'US',
            'province_code': 'CA',
        }, GeoCodes.parse('NA-US-CA'))

    def test_country_to_code(self):
        self.assertEquals('NA-US', GeoCodes.country_to_code('US'))
        self.assertEquals('EU-GB', GeoCodes.country_to_code('GB'))
        self.assertFalse(GeoCodes.country_to_code('XX'))

    def test_province_to_code(self):
        self.assertEquals('NA-US-OR', GeoCodes.province_to_code('OR'))
        self.assertEquals('NA-US-KY', GeoCodes.province_to_code('KY'))
        self.assertFalse(GeoCodes.province_to_code('XX'))
