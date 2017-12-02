#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from octodns.provider.plan import PlanLogger


class TestPlanLogger(TestCase):

    def test_invalid_level(self):
        with self.assertRaises(Exception) as ctx:
            PlanLogger('invalid', 'not-a-level')
        self.assertEquals('Unsupported level: not-a-level',
                          ctx.exception.message)
