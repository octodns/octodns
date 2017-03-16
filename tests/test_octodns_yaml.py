#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from StringIO import StringIO
from unittest import TestCase
from yaml.constructor import ConstructorError

from octodns.yaml import safe_dump, safe_load


class TestYaml(TestCase):

    def test_stuff(self):
        self.assertEquals({
            1: 'a',
            2: 'b',
            '3': 'c',
            10: 'd',
            '11': 'e',
        }, safe_load('''
1: a
2: b
'3': c
10: d
'11': e
'''))

        self.assertEquals({
            '*.1.2': 'a',
            '*.2.2': 'b',
            '*.10.1': 'c',
            '*.11.2': 'd',
        }, safe_load('''
'*.1.2': 'a'
'*.2.2': 'b'
'*.10.1': 'c'
'*.11.2': 'd'
'''))

        with self.assertRaises(ConstructorError) as ctx:
            safe_load('''
'*.2.2': 'b'
'*.1.2': 'a'
'*.11.2': 'd'
'*.10.1': 'c'
''')
        self.assertEquals('keys out of order: *.2.2, *.1.2, *.11.2, *.10.1',
                          ctx.exception.problem)

        buf = StringIO()
        safe_dump({
            '*.1.1': 42,
            '*.11.1': 43,
            '*.2.1': 44,
        }, buf)
        self.assertEquals("---\n'*.1.1': 42\n'*.2.1': 44\n'*.11.1': 43\n",
                          buf.getvalue())
