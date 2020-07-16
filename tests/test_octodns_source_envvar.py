from six import text_type
from unittest import TestCase
from unittest.mock import patch

from octodns.source.envvar import EnvVarSource
from octodns.source.envvar import EnvironmentVariableNotFoundException
from octodns.zone import Zone


class TestEnvVarSource(TestCase):

    def test_read_variable(self):
        envvar = 'OCTODNS_TEST_ENVIRONMENT_VARIABLE'
        source = EnvVarSource('testid', envvar, 'recordname', ttl=120)
        with self.assertRaises(EnvironmentVariableNotFoundException) as ctx:
            source._read_variable()
        msg = 'Unknown environment variable {}'.format(envvar)
        self.assertEquals(msg, text_type(ctx.exception))

        with patch.dict('os.environ', {envvar: 'testvalue'}):
            source._read_variable()
        self.assertEquals(source.value, 'testvalue')

    def test_populate(self):
        envvar = 'TEST_VAR'
        value = 'somevalue'
        record = 'testrecord'
        source = EnvVarSource('testid', envvar, record)
        zone = Zone('unit.tests.', [])

        with patch.dict('os.environ', {envvar: value}):
            source.populate(zone)

        # TODO: Validate zone and record
