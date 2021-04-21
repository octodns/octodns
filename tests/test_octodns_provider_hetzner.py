#
#
#


from __future__ import absolute_import, division, print_function, \
    unicode_literals

from os.path import dirname, join
from requests import HTTPError
from requests_mock import ANY, mock as requests_mock
from six import text_type
from unittest import TestCase

from octodns.provider.hetzner import HetznerProvider
from octodns.provider.yaml import YamlProvider
from octodns.zone import Zone


class TestdHetznerProvider(TestCase):
    expected = Zone('unit.tests.', [])
    source = YamlProvider('test', join(dirname(__file__), 'config'))
    source.populate(expected)

    def test_populate(self):
        provider = HetznerProvider('test', 'token')

        # Bad auth
        with requests_mock() as mock:
            mock.get(ANY, status_code=401,
                     text='{"message":"Invalid authentication credentials"}')

            with self.assertRaises(Exception) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals('Unauthorized', text_type(ctx.exception))

        # General error
        with requests_mock() as mock:
            mock.get(ANY, status_code=502, text='Things caught fire')

            with self.assertRaises(HTTPError) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals(502, ctx.exception.response.status_code)

        # Non-existent zone doesn't populate anything
        with requests_mock() as mock:
            mock.get(ANY, status_code=404,
                     text='{"zone":{"id":"","name":"","ttl":0,"registrar":"",'
                     '"legacy_dns_host":"","legacy_ns":null,"ns":null,'
                     '"created":"","verified":"","modified":"","project":"",'
                     '"owner":"","permission":"","zone_type":{"id":"",'
                     '"name":"","description":"","prices":null},"status":"",'
                     '"paused":false,"is_secondary_dns":false,'
                     '"txt_verification":{"name":"","token":""},'
                     '"records_count":0},"error":{'
                     '"message":"zone not found","code":404}}')

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(set(), zone.records)

        # No diffs == no changes
        with requests_mock() as mock:
            base = 'https://dns.hetzner.com/api/v1'
            with open('tests/fixtures/hetzner-zones.json') as fh:
                mock.get('{}/zones'.format(base), text=fh.read())
            with open('tests/fixtures/hetzner-records.json') as fh:
                mock.get('{}/records'.format(base), text=fh.read())

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(13, len(zone.records))
            changes = self.expected.changes(zone, provider)
            self.assertEquals(0, len(changes))

        # 2nd populate makes no network calls/all from cache
        again = Zone('unit.tests.', [])
        provider.populate(again)
        self.assertEquals(13, len(again.records))

        # bust the cache
        del provider._zone_records[zone.name]
