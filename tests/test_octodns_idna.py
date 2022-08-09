#
#
#

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

from octodns.idna import idna_decode, idna_encode


class TestIdna(TestCase):
    def assertIdna(self, value, expected):
        got = idna_encode(value)
        self.assertEqual(expected, got)
        # round tripped
        self.assertEqual(value, idna_decode(got))

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
        self.assertIdna(
            'zajęzyk.zajęzyk.pl.', 'xn--zajzyk-y4a.xn--zajzyk-y4a.pl.'
        )

        self.assertIdna('déjàvu.com.', 'xn--djvu-1na6c.com.')
        self.assertIdna('déjà-vu.com.', 'xn--dj-vu-sqa5d.com.')

    def test_underscores(self):
        # underscores aren't valid in idna names, so these are all ascii

        self.assertIdna('foo_bar.pl.', 'foo_bar.pl.')
        self.assertIdna('bleep_bloop.foo_bar.pl.', 'bleep_bloop.foo_bar.pl.')

    def test_case_insensitivity(self):
        # Shouldn't be hit by octoDNS use cases, but checked anyway
        self.assertEqual('zajęzyk.pl.', idna_decode('XN--ZAJZYK-Y4A.PL.'))
