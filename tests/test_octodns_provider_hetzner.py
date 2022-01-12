#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase


class TestHetznerShim(TestCase):

    def test_missing(self):
        with self.assertRaises(ModuleNotFoundError):
            from octodns.provider.hetzner import HetznerProvider
            HetznerProvider
