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
            value = source._read_variable()
        self.assertEquals(value, 'testvalue')

    def test_populate(self):
        envvar = 'TEST_VAR'
        value = 'somevalue'
        name = 'testrecord'
        zone_name = 'unit.tests.'
        source = EnvVarSource('testid', envvar, name)
        zone = Zone(zone_name, [])

        with patch.dict('os.environ', {envvar: value}):
            source.populate(zone)

        self.assertEquals(1, len(zone.records))
        record = list(zone.records)[0]
        self.assertEquals(name, record.name)
        self.assertEquals('{}.{}'.format(name, zone_name), record.fqdn)
        self.assertEquals('TXT', record._type)
        self.assertEquals(1, len(record.values))
        self.assertEquals(value, record.values[0])
