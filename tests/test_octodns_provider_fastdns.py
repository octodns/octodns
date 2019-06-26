#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from mock import Mock, call
from os.path import dirname, join
from requests import HTTPError
from requests_mock import ANY, mock as requests_mock
from unittest import TestCase

from octodns.record import Record
from octodns.provider.fastdns import AkamaiProvider, AkamaiClientException
from octodns.provider.yaml import YamlProvider
from octodns.zone import Zone


class TestFastdnsProvider(TestCase):
    expected = Zone('unit.tests.', [])
    source = YamlProvider('test', join(dirname(__file__), 'config'))
    source.populate(expected)

    def test_populate(self):
        provider = AkamaiProvider("test", "client_secret", "host", "access_token", 
                                  "client_token")
        
        # Bad Auth
        with requests_mock() as mock:
            mock.get(ANY, status_code=401,
                     text='{"message": "Authentication failed"}')

            with self.assertRaises(Exception) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals("401: Unauthorized", ctx.exception.message)

        # general error
        with requests_mock() as mock:
            mock.get(ANY, status_code=502, text='Things caught fire')

            with self.assertRaises(HTTPError) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals(502, ctx.exception.response.status_code)

         # Non-existant zone doesn't populate anything
        with requests_mock() as mock:
            mock.get(ANY, status_code=404,
                     text='{"message": "Domain `foo.bar` not found"}')

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(set(), zone.records)

        # # No diffs == no changes
        # with requests_mock() as mock:
        #     base = 'https://api.dnsimple.com/v2/42/zones/unit.tests/' \
        #         'records?page='
        #     with open('tests/fixtures/dnsimple-page-1.json') as fh:
        #         mock.get('{}{}'.format(base, 1), text=fh.read())
        #     with open('tests/fixtures/dnsimple-page-2.json') as fh:
        #         mock.get('{}{}'.format(base, 2), text=fh.read())

        #     zone = Zone('unit.tests.', [])
        #     provider.populate(zone)
        #     self.assertEquals(16, len(zone.records))
        #     changes = self.expected.changes(zone, provider)
        #     self.assertEquals(0, len(changes))