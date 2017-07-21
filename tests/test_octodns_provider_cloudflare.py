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
from octodns.provider.cloudflare import CloudflareProvider
from octodns.provider.yaml import YamlProvider
from octodns.zone import Zone


class TestCloudflareProvider(TestCase):
    expected = Zone('unit.tests.', [])
    source = YamlProvider('test', join(dirname(__file__), 'config'))
    source.populate(expected)

    # Our test suite differs a bit, add our NS and remove the simple one
    expected.add_record(Record.new(expected, 'under', {
        'ttl': 3600,
        'type': 'NS',
        'values': [
            'ns1.unit.tests.',
            'ns2.unit.tests.',
        ]
    }))
    for record in list(expected.records):
        if record.name == 'sub' and record._type == 'NS':
            expected._remove_record(record)
            break

    empty = {'result': [], 'result_info': {'count': 0, 'per_page': 0}}

    def test_populate(self):
        provider = CloudflareProvider('test', 'email', 'token')

        # Bad auth
        with requests_mock() as mock:
            mock.get(ANY, status_code=403,
                     text='{"success":false,"errors":[{"code":9103,'
                     '"message":"Unknown X-Auth-Key or X-Auth-Email"}],'
                     '"messages":[],"result":null}')

            with self.assertRaises(Exception) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals('Unknown X-Auth-Key or X-Auth-Email',
                              ctx.exception.message)

        # Bad auth, unknown resp
        with requests_mock() as mock:
            mock.get(ANY, status_code=403, text='{}')

            with self.assertRaises(Exception) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals('Authentication error', ctx.exception.message)

        # General error
        with requests_mock() as mock:
            mock.get(ANY, status_code=502, text='Things caught fire')

            with self.assertRaises(HTTPError) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals(502, ctx.exception.response.status_code)

        # Non-existant zone doesn't populate anything
        with requests_mock() as mock:
            mock.get(ANY, status_code=200, json=self.empty)

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(set(), zone.records)

        # re-populating the same non-existant zone uses cache and makes no
        # calls
        again = Zone('unit.tests.', [])
        provider.populate(again)
        self.assertEquals(set(), again.records)

        # bust zone cache
        provider._zones = None

        # existing zone with data
        with requests_mock() as mock:
            base = 'https://api.cloudflare.com/client/v4/zones'

            # zones
            with open('tests/fixtures/cloudflare-zones-page-1.json') as fh:
                mock.get('{}?page=1'.format(base), status_code=200,
                         text=fh.read())
            with open('tests/fixtures/cloudflare-zones-page-2.json') as fh:
                mock.get('{}?page=2'.format(base), status_code=200,
                         text=fh.read())
            mock.get('{}?page=3'.format(base), status_code=200,
                     json={'result': [], 'result_info': {'count': 0,
                                                         'per_page': 0}})

            # records
            base = '{}/234234243423aaabb334342aaa343435/dns_records' \
                .format(base)
            with open('tests/fixtures/cloudflare-dns_records-'
                      'page-1.json') as fh:
                mock.get('{}?page=1'.format(base), status_code=200,
                         text=fh.read())
            with open('tests/fixtures/cloudflare-dns_records-'
                      'page-2.json') as fh:
                mock.get('{}?page=2'.format(base), status_code=200,
                         text=fh.read())

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(9, len(zone.records))

            changes = self.expected.changes(zone, provider)
            self.assertEquals(0, len(changes))

        # re-populating the same zone/records comes out of cache, no calls
        again = Zone('unit.tests.', [])
        provider.populate(again)
        self.assertEquals(9, len(again.records))

    def test_apply(self):
        provider = CloudflareProvider('test', 'email', 'token')

        provider._request = Mock()

        provider._request.side_effect = [
            self.empty,  # no zones
            {
                'result': {
                    'id': 42,
                }
            },  # zone create
        ] + [None] * 16  # individual record creates

        # non-existant zone, create everything
        plan = provider.plan(self.expected)
        self.assertEquals(9, len(plan.changes))
        self.assertEquals(9, provider.apply(plan))

        provider._request.assert_has_calls([
            # created the domain
            call('POST', '/zones', data={
                'jump_start': False,
                'name': 'unit.tests'
            }),
            # created at least one of the record with expected data
            call('POST', '/zones/42/dns_records', data={
                'content': 'ns1.unit.tests.',
                'type': 'NS',
                'name': 'under.unit.tests',
                'ttl': 3600
            }),
            # make sure semicolons are not escaped when sending data
            call('POST', '/zones/42/dns_records', data={
                'content': 'v=DKIM1;k=rsa;s=email;h=sha256;'
                           'p=A/kinda+of/long/string+with+numb3rs',
                'type': 'TXT',
                'name': 'txt.unit.tests',
                'ttl': 600
            }),
        ], True)
        # expected number of total calls
        self.assertEquals(18, provider._request.call_count)

        provider._request.reset_mock()

        provider.zone_records = Mock(return_value=[
            {
                "id": "fc12ab34cd5611334422ab3322997653",
                "type": "A",
                "name": "www.unit.tests",
                "content": "1.2.3.4",
                "proxiable": True,
                "proxied": False,
                "ttl": 300,
                "locked": False,
                "zone_id": "ff12ab34cd5611334422ab3322997650",
                "zone_name": "unit.tests",
                "modified_on": "2017-03-11T18:01:43.420689Z",
                "created_on": "2017-03-11T18:01:43.420689Z",
                "meta": {
                    "auto_added": False
                }
            },
            {
                "id": "fc12ab34cd5611334422ab3322997654",
                "type": "A",
                "name": "www.unit.tests",
                "content": "2.2.3.4",
                "proxiable": True,
                "proxied": False,
                "ttl": 300,
                "locked": False,
                "zone_id": "ff12ab34cd5611334422ab3322997650",
                "zone_name": "unit.tests",
                "modified_on": "2017-03-11T18:01:44.030044Z",
                "created_on": "2017-03-11T18:01:44.030044Z",
                "meta": {
                    "auto_added": False
                }
            },
            {
                "id": "fc12ab34cd5611334422ab3322997655",
                "type": "A",
                "name": "nc.unit.tests",
                "content": "3.2.3.4",
                "proxiable": True,
                "proxied": False,
                "ttl": 120,
                "locked": False,
                "zone_id": "ff12ab34cd5611334422ab3322997650",
                "zone_name": "unit.tests",
                "modified_on": "2017-03-11T18:01:44.030044Z",
                "created_on": "2017-03-11T18:01:44.030044Z",
                "meta": {
                    "auto_added": False
                }
            },
            {
                "id": "fc12ab34cd5611334422ab3322997655",
                "type": "A",
                "name": "ttl.unit.tests",
                "content": "4.2.3.4",
                "proxiable": True,
                "proxied": False,
                "ttl": 600,
                "locked": False,
                "zone_id": "ff12ab34cd5611334422ab3322997650",
                "zone_name": "unit.tests",
                "modified_on": "2017-03-11T18:01:44.030044Z",
                "created_on": "2017-03-11T18:01:44.030044Z",
                "meta": {
                    "auto_added": False
                }
            },
        ])

        # we don't care about the POST/create return values
        provider._request.return_value = {}
        provider._request.side_effect = None

        wanted = Zone('unit.tests.', [])
        wanted.add_record(Record.new(wanted, 'nc', {
            'ttl': 60,  # TTL is below their min
            'type': 'A',
            'value': '3.2.3.4'
        }))
        wanted.add_record(Record.new(wanted, 'ttl', {
            'ttl': 300,  # TTL change
            'type': 'A',
            'value': '3.2.3.4'
        }))

        plan = provider.plan(wanted)
        # only see the delete & ttl update, below min-ttl is filtered out
        self.assertEquals(2, len(plan.changes))
        self.assertEquals(2, provider.apply(plan))
        # recreate for update, and deletes for the 2 parts of the other
        provider._request.assert_has_calls([
            call('POST', '/zones/42/dns_records', data={
                'content': '3.2.3.4',
                'type': 'A',
                'name': 'ttl.unit.tests',
                'ttl': 300}),
            call('DELETE', '/zones/ff12ab34cd5611334422ab3322997650/'
                 'dns_records/fc12ab34cd5611334422ab3322997655'),
            call('DELETE', '/zones/ff12ab34cd5611334422ab3322997650/'
                 'dns_records/fc12ab34cd5611334422ab3322997653'),
            call('DELETE', '/zones/ff12ab34cd5611334422ab3322997650/'
                 'dns_records/fc12ab34cd5611334422ab3322997654')
        ])
