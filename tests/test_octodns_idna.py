#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from octodns.idna import idna_decode, idna_encode


class TestIdna(TestCase):

    def assertIdna(self, value, expected):
        got = idna_encode(value)
        self.assertEqual(expected, got)
        # round tripped
        self.assertEqual(value, idna_decode(value))

    def test_noops(self):
        # empty
        self.assertIdna('', '')

        # noop
        self.assertIdna('unit.tests.', 'unit.tests.')

        # wildcard noop
        self.assertIdna('*.unit.tests.', '*.unit.tests.')

    def test_unicode(self):
        # encoded
        self.assertIdna('zajęzyk.pl.', 'xn--zajzyk-y4a.pl.')

        # encoded with wildcard
        self.assertIdna('*.zajęzyk.pl.', '*.xn--zajzyk-y4a.pl.')

        # encoded with simple name
        self.assertIdna('noop.zajęzyk.pl.', 'noop.xn--zajzyk-y4a.pl.')

        # encoded with encoded name
        self.assertIdna('zajęzyk.zajęzyk.pl.',
                        'xn--zajzyk-y4a.xn--zajzyk-y4a.pl.')
