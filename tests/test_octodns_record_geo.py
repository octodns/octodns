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
