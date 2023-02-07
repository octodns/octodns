from unittest import TestCase
from unittest.mock import patch

from octodns.source.envvar import (
    EnvironmentVariableNotFoundException,
    EnvVarSource,
)
from octodns.zone import Zone


class TestEnvVarSource(TestCase):
    def test_read_variable(self):
        envvar = 'OCTODNS_TEST_ENVIRONMENT_VARIABLE'
        source = EnvVarSource('testid', envvar, 'recordname', ttl=120)
        with self.assertRaises(EnvironmentVariableNotFoundException) as ctx:
            source._read_variable()
        msg = f'Unknown environment variable {envvar}'
        self.assertEqual(msg, str(ctx.exception))

        with patch.dict('os.environ', {envvar: 'testvalue'}):
            value = source._read_variable()
        self.assertEqual(value, 'testvalue')

    def test_populate(self):
        envvar = 'TEST_VAR'
        value = 'somevalue'
        name = 'testrecord'
        zone_name = 'unit.tests.'
        source = EnvVarSource('testid', envvar, name)
        zone = Zone(zone_name, [])

        with patch.dict('os.environ', {envvar: value}):
            source.populate(zone)

        self.assertEqual(1, len(zone.records))
        record = list(zone.records)[0]
        self.assertEqual(name, record.name)
        self.assertEqual(f'{name}.{zone_name}', record.fqdn)
        self.assertEqual('TXT', record._type)
        self.assertEqual(1, len(record.values))
        self.assertEqual(value, record.values[0])
