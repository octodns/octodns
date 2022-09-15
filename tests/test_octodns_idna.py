#
#
#

from unittest import TestCase

from octodns.idna import IdnaDict, IdnaError, idna_decode, idna_encode


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
        self.assertEqual('zajęzyk.pl.', idna_decode('XN--ZAJZYK-Y4A.PL.'))
        self.assertEqual('xn--zajzyk-y4a.pl.', idna_encode('ZajęzyK.Pl.'))

    def test_repeated_encode_decoded(self):
        self.assertEqual(
            'zajęzyk.pl.', idna_decode(idna_decode('xn--zajzyk-y4a.pl.'))
        )
        self.assertEqual(
            'xn--zajzyk-y4a.pl.', idna_encode(idna_encode('zajęzyk.pl.'))
        )

    def test_exception_translation(self):
        with self.assertRaises(IdnaError) as ctx:
            idna_encode('déjà..vu.')
        self.assertEqual('Empty Label', str(ctx.exception))

        with self.assertRaises(IdnaError) as ctx:
            idna_decode('xn--djvu-1na6c..com.')
        self.assertEqual('Empty Label', str(ctx.exception))


class TestIdnaDict(TestCase):
    plain = 'testing.tests.'
    almost = 'tésting.tests.'
    utf8 = 'déjà.vu.'

    normal = {plain: 42, almost: 43, utf8: 44}

    def test_basics(self):
        d = IdnaDict()

        # plain ascii
        d[self.plain] = 42
        self.assertEqual(42, d[self.plain])

        # almost the same, single utf-8 char
        d[self.almost] = 43
        # fetch as utf-8
        self.assertEqual(43, d[self.almost])
        # fetch as idna
        self.assertEqual(43, d[idna_encode(self.almost)])
        # plain is stil there, unchanged
        self.assertEqual(42, d[self.plain])

        # lots of utf8
        d[self.utf8] = 44
        self.assertEqual(44, d[self.utf8])
        self.assertEqual(44, d[idna_encode(self.utf8)])

        # setting with idna version replaces something set previously with utf8
        d[idna_encode(self.almost)] = 45
        self.assertEqual(45, d[self.almost])
        self.assertEqual(45, d[idna_encode(self.almost)])

        # contains
        self.assertTrue(self.plain in d)
        self.assertTrue(self.almost in d)
        self.assertTrue(idna_encode(self.almost) in d)
        self.assertTrue(self.utf8 in d)
        self.assertTrue(idna_encode(self.utf8) in d)

        # we can delete with either form
        del d[self.almost]
        self.assertFalse(self.almost in d)
        self.assertFalse(idna_encode(self.almost) in d)
        del d[idna_encode(self.utf8)]
        self.assertFalse(self.utf8 in d)
        self.assertFalse(idna_encode(self.utf8) in d)

        # smoke test of repr
        d.__repr__()

    def test_keys(self):
        d = IdnaDict(self.normal)

        # keys are idna versions by default
        self.assertEqual(
            (self.plain, idna_encode(self.almost), idna_encode(self.utf8)),
            tuple(d.keys()),
        )

        # decoded keys gives the utf8 version
        self.assertEqual(
            (self.plain, self.almost, self.utf8), tuple(d.decoded_keys())
        )

    def test_items(self):
        d = IdnaDict(self.normal)

        # idna keys in items
        self.assertEqual(
            (
                (self.plain, 42),
                (idna_encode(self.almost), 43),
                (idna_encode(self.utf8), 44),
            ),
            tuple(d.items()),
        )

        # utf8 keys in decoded_items
        self.assertEqual(
            ((self.plain, 42), (self.almost, 43), (self.utf8, 44)),
            tuple(d.decoded_items()),
        )
