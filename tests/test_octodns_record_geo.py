#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from octodns.record.geo import GeoCodes


class TestRecordGeoCodes(TestCase):

    def test_validate(self):
        # All valid
        self.assertEquals([], GeoCodes.validate('NA'))
        self.assertEquals([], GeoCodes.validate('NA-US'))
        self.assertEquals([], GeoCodes.validate('NA-US-OR'))

        # Just plain bad
        self.assertEquals(['Invalid geo code "XX-YY-ZZ-AA"'],
                          GeoCodes.validate('XX-YY-ZZ-AA'))
        self.assertEquals(['Unknown continent code "X-Y-Z"'],
                          GeoCodes.validate('X-Y-Z'))
        self.assertEquals(['Unknown continent code "XXX-Y-Z"'],
                          GeoCodes.validate('XXX-Y-Z'))

        # Bad continent
        self.assertEquals(['Unknown continent code "XX"'],
                          GeoCodes.validate('XX'))
        # Bad continent good country
        self.assertEquals(['Unknown continent code "XX-US"'],
                          GeoCodes.validate('XX-US'))
        # Bad continent good country and province
        self.assertEquals(['Unknown continent code "XX-US-OR"'],
                          GeoCodes.validate('XX-US-OR'))

        # Bad country, good continent
        self.assertEquals(['Unknown country code "NA-XX"'],
                          GeoCodes.validate('NA-XX'))
        # Bad country, good continent and state
        self.assertEquals(['Unknown country code "NA-XX-OR"'],
                          GeoCodes.validate('NA-XX-OR'))
        # Good country, good continent, but bad match
        self.assertEquals(['Unknown country code "NA-GB"'],
                          GeoCodes.validate('NA-GB'))

        # Bad province code, good continent and country
        self.assertEquals(['Unknown province code "NA-US-XX"'],
                          GeoCodes.validate('NA-US-XX'))
