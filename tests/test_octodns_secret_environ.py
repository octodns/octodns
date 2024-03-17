#
#
#

from os import environ
from unittest import TestCase

from octodns.context import ContextDict
from octodns.secret.environ import EnvironSecrets, EnvironSecretsException


class TestEnvironSecrets(TestCase):
    def test_environ_secrets(self):
        # put some secrets into our env
        environ['THIS_EXISTS'] = 'and has a val'
        environ['THIS_IS_AN_INT'] = '42'
        environ['THIS_IS_A_FLOAT'] = '43.44'

        es = EnvironSecrets('env')

        source = ContextDict({}, context='xyz')
        v = es.fetch('THIS_EXISTS', source)
        self.assertEqual('and has a val', v)
        self.assertIsInstance(v, str)

        v = es.fetch('THIS_IS_AN_INT', source)
        self.assertEqual(42, v)
        self.assertIsInstance(v, int)

        v = es.fetch('THIS_IS_A_FLOAT', source)
        self.assertEqual(43.44, v)
        self.assertIsInstance(v, float)

        with self.assertRaises(EnvironSecretsException) as ctx:
            es.fetch('DOES_NOT_EXIST', source)
        self.assertEqual(
            'Incorrect provider config, missing env var DOES_NOT_EXIST, xyz',
            str(ctx.exception),
        )
