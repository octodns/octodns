#
#
#

from io import StringIO
from unittest import TestCase

from yaml.constructor import ConstructorError

from octodns.yaml import InvalidOrder, safe_dump, safe_load


class TestYaml(TestCase):
    def test_stuff(self):
        self.assertEqual(
            {1: 'a', 2: 'b', '3': 'c', 10: 'd', '11': 'e'},
            safe_load(
                '''
1: a
2: b
'3': c
10: d
'11': e
'''
            ),
        )

        self.assertEqual(
            {'*.1.2': 'a', '*.2.2': 'b', '*.10.1': 'c', '*.11.2': 'd'},
            safe_load(
                '''
'*.1.2': 'a'
'*.2.2': 'b'
'*.10.1': 'c'
'*.11.2': 'd'
'''
            ),
        )

        with self.assertRaises(ConstructorError) as ctx:
            safe_load(
                '''
'*.2.2': 'b'
'*.1.2': 'a'
'*.11.2': 'd'
'*.10.1': 'c'
'''
            )
        self.assertTrue(
            'keys out of order: expected *.1.2 got *.2.2 at'
            in ctx.exception.problem
        )

        buf = StringIO()
        safe_dump({'*.1.1': 42, '*.11.1': 43, '*.2.1': 44}, buf)
        self.assertEqual(
            "---\n'*.1.1': 42\n'*.2.1': 44\n'*.11.1': 43\n", buf.getvalue()
        )

        # hex sorting isn't ideal, not treated as hex, this make sure we don't
        # change the behavior
        buf = StringIO()
        safe_dump({'45a03129': 42, '45a0392a': 43}, buf)
        self.assertEqual("---\n45a0392a: 43\n45a03129: 42\n", buf.getvalue())

    def test_include(self):
        with open('tests/config/include/main.yaml') as fh:
            data = safe_load(fh)
        self.assertEqual(
            {
                'included-array': [14, 15, 16, 72],
                'included-dict': {'k': 'v', 'z': 42},
                'included-empty': None,
                'included-nested': 'Hello World!',
                'included-subdir': 'Hello World!',
                'key': 'value',
                'name': 'main',
            },
            data,
        )

        with open('tests/config/include/include-doesnt-exist.yaml') as fh:
            with self.assertRaises(FileNotFoundError) as ctx:
                data = safe_load(fh)
            self.assertEqual(
                "[Errno 2] No such file or directory: 'tests/config/include/does-not-exist.yaml'",
                str(ctx.exception),
            )

    def test_order_mode(self):
        data = {'*.1.2': 'a', '*.10.1': 'c', '*.11.2': 'd', '*.2.2': 'b'}
        natural = '''---
'*.1.2': a
'*.2.2': b
'*.10.1': c
'*.11.2': d
'''
        simple = '''---
'*.1.2': a
'*.10.1': c
'*.11.2': d
'*.2.2': b
'''

        ## natural
        # correct order
        self.assertEqual(data, safe_load(natural))
        # wrong order
        with self.assertRaises(ConstructorError) as ctx:
            safe_load(simple)
        problem = ctx.exception.problem.split(' at')[0]
        self.assertEqual(
            'keys out of order: expected *.2.2 got *.10.1', problem
        )
        # dump
        buf = StringIO()
        safe_dump(data, buf)
        self.assertEqual(natural, buf.getvalue())

        ## simple
        # correct order
        self.assertEqual(data, safe_load(simple, order_mode='simple'))
        # wrong order
        with self.assertRaises(ConstructorError) as ctx:
            safe_load(natural, order_mode='simple')
        problem = ctx.exception.problem.split(' at')[0]
        self.assertEqual(
            'keys out of order: expected *.10.1 got *.2.2', problem
        )
        buf = StringIO()
        safe_dump(data, buf, order_mode='simple')
        self.assertEqual(simple, buf.getvalue())

        with self.assertRaises(InvalidOrder) as ctx:
            safe_load(None, order_mode='bad')
        self.assertEqual(
            'Invalid order_mode, "bad", options are "natural", "simple"',
            str(ctx.exception),
        )
        with self.assertRaises(InvalidOrder) as ctx:
            safe_dump(None, None, order_mode='bad2')
        self.assertEqual(
            'Invalid order_mode, "bad2", options are "natural", "simple"',
            str(ctx.exception),
        )
