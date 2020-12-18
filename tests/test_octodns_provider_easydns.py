#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import json
from mock import Mock, call
from os.path import dirname, join
from requests import HTTPError
from requests_mock import ANY, mock as requests_mock
from six import text_type
from unittest import TestCase

from octodns.record import Record
from octodns.provider.easydns import EasyDNSClientNotFound, \
    EasyDNSProvider
from octodns.provider.yaml import YamlProvider
from octodns.zone import Zone


class TestEasyDNSProvider(TestCase):
    expected = Zone('unit.tests.', [])
    source = YamlProvider('test', join(dirname(__file__), 'config'))
    source.populate(expected)

    def test_populate(self):
        provider = EasyDNSProvider('test', 'token', 'apikey')

        # Bad auth
        with requests_mock() as mock:
            mock.get(ANY, status_code=401,
                     text='{"id":"unauthorized",'
                     '"message":"Unable to authenticate you."}')

            with self.assertRaises(Exception) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals('Unauthorized', text_type(ctx.exception))

        # Bad request
        with requests_mock() as mock:
            mock.get(ANY, status_code=400,
                     text='{"id":"invalid",'
                     '"message":"Bad request"}')

            with self.assertRaises(Exception) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals('Bad request', text_type(ctx.exception))

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
                     text='{"id":"not_found","message":"The resource you '
                     'were accessing could not be found."}')

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(set(), zone.records)

        # No diffs == no changes
        with requests_mock() as mock:
            base = 'https://rest.easydns.net/zones/records/'
            with open('tests/fixtures/easydns-records.json') as fh:
                mock.get('{}{}'.format(base, 'parsed/unit.tests'),
                         text=fh.read())
            with open('tests/fixtures/easydns-records.json') as fh:
                mock.get('{}{}'.format(base, 'all/unit.tests'),
                         text=fh.read())

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

    def test_domain(self):
        provider = EasyDNSProvider('test', 'token', 'apikey')

        with requests_mock() as mock:
            base = 'https://rest.easydns.net/'
            mock.get('{}{}'.format(base, 'domain/unit.tests'), status_code=400,
                     text='{"id":"not_found","message":"The resource you '
                     'were accessing could not be found."}')

            with self.assertRaises(Exception) as ctx:
                provider._client.domain('unit.tests')

            self.assertEquals('Not Found', text_type(ctx.exception))

    def test_apply_not_found(self):
        provider = EasyDNSProvider('test', 'token', 'apikey')

        wanted = Zone('unit.tests.', [])
        wanted.add_record(Record.new(wanted, 'test1', {
            "name": "test1",
            "ttl": 300,
            "type": "A",
            "value": "1.2.3.4",
        }))

        with requests_mock() as mock:
            base = 'https://rest.easydns.net/'
            mock.get('{}{}'.format(base, 'domain/unit.tests'), status_code=404,
                     text='{"id":"not_found","message":"The resource you '
                     'were accessing could not be found."}')
            mock.put('{}{}'.format(base, 'domains/add/unit.tests'),
                     status_code=200,
                     text='{"id":"OK","message":"Zone created."}')
            mock.get('{}{}'.format(base, 'zones/records/parsed/unit.tests'),
                     status_code=404,
                     text='{"id":"not_found","message":"The resource you '
                     'were accessing could not be found."}')
            mock.get('{}{}'.format(base, 'zones/records/all/unit.tests'),
                     status_code=404,
                     text='{"id":"not_found","message":"The resource you '
                     'were accessing could not be found."}')

            plan = provider.plan(wanted)
            self.assertFalse(plan.exists)
            self.assertEquals(1, len(plan.changes))
            with self.assertRaises(Exception) as ctx:
                provider.apply(plan)

            self.assertEquals('Not Found', text_type(ctx.exception))

    def test_domain_create(self):
        provider = EasyDNSProvider('test', 'token', 'apikey')
        domain_after_creation = {
            "tm": 1000000000,
            "data": [{
                "id": "12341001",
                "domain": "unit.tests",
                "host": "@",
                "ttl": "0",
                "prio": "0",
                "type": "SOA",
                "rdata": "dns1.easydns.com. zone.easydns.com. "
                "2020010101 3600 600 604800 0",
                "geozone_id": "0",
                "last_mod": "2020-01-01 01:01:01"
            }, {
                "id": "12341002",
                "domain": "unit.tests",
                "host": "@",
                "ttl": "0",
                "prio": "0",
                "type": "NS",
                "rdata": "LOCAL.",
                "geozone_id": "0",
                "last_mod": "2020-01-01 01:01:01"
            }, {
                "id": "12341003",
                "domain": "unit.tests",
                "host": "@",
                "ttl": "0",
                "prio": "0",
                "type": "MX",
                "rdata": "LOCAL.",
                "geozone_id": "0",
                "last_mod": "2020-01-01 01:01:01"
            }],
            "count": 3,
            "total": 3,
            "start": 0,
            "max": 1000,
            "status": 200
        }
        with requests_mock() as mock:
            base = 'https://rest.easydns.net/'
            mock.put('{}{}'.format(base, 'domains/add/unit.tests'),
                     status_code=201, text='{"id":"OK"}')
            mock.get('{}{}'.format(base, 'zones/records/all/unit.tests'),
                     text=json.dumps(domain_after_creation))
            mock.delete(ANY, text='{"id":"OK"}')
            provider._client.domain_create('unit.tests')

    def test_caa(self):
        provider = EasyDNSProvider('test', 'token', 'apikey')

        # Invalid rdata records
        caa_record_invalid = [{
            "domain": "unit.tests",
            "host": "@",
            "ttl": "3600",
            "prio": "0",
            "type": "CAA",
            "rdata": "0",
        }]

        # Valid rdata records
        caa_record_valid = [{
            "domain": "unit.tests",
            "host": "@",
            "ttl": "3600",
            "prio": "0",
            "type": "CAA",
            "rdata": "0 issue ca.unit.tests",
        }]

        provider._data_for_CAA('CAA', caa_record_invalid)
        provider._data_for_CAA('CAA', caa_record_valid)

    def test_naptr(self):
        provider = EasyDNSProvider('test', 'token', 'apikey')

        # Invalid rdata records
        naptr_record_invalid = [{
            "domain": "unit.tests",
            "host": "naptr",
            "ttl": "600",
            "prio": "10",
            "type": "NAPTR",
            "rdata": "100",
        }]

        # Valid rdata records
        naptr_record_valid = [{
            "domain": "unit.tests",
            "host": "naptr",
            "ttl": "600",
            "prio": "10",
            "type": "NAPTR",
            "rdata": "10 10 'U' 'SIP+D2U' '!^.*$!sip:info@bar.example.com!' .",
        }]

        provider._data_for_NAPTR('NAPTR', naptr_record_invalid)
        provider._data_for_NAPTR('NAPTR', naptr_record_valid)

    def test_srv(self):
        provider = EasyDNSProvider('test', 'token', 'apikey')

        # Invalid rdata records
        srv_invalid = [{
            "domain": "unit.tests",
            "host": "_srv._tcp",
            "ttl": "600",
            "type": "SRV",
            "rdata": "",
        }]
        srv_invalid2 = [{
            "domain": "unit.tests",
            "host": "_srv._tcp",
            "ttl": "600",
            "type": "SRV",
            "rdata": "11",
        }]
        srv_invalid3 = [{
            "domain": "unit.tests",
            "host": "_srv._tcp",
            "ttl": "600",
            "type": "SRV",
            "rdata": "12 30",
        }]
        srv_invalid4 = [{
            "domain": "unit.tests",
            "host": "_srv._tcp",
            "ttl": "600",
            "type": "SRV",
            "rdata": "13 40 1234",
        }]

        # Valid rdata
        srv_valid = [{
            "domain": "unit.tests",
            "host": "_srv._tcp",
            "ttl": "600",
            "type": "SRV",
            "rdata": "100 20 5678 foo-2.unit.tests.",
        }]

        srv_invalid_content = provider._data_for_SRV('SRV', srv_invalid)
        srv_invalid_content2 = provider._data_for_SRV('SRV', srv_invalid2)
        srv_invalid_content3 = provider._data_for_SRV('SRV', srv_invalid3)
        srv_invalid_content4 = provider._data_for_SRV('SRV', srv_invalid4)
        srv_valid_content = provider._data_for_SRV('SRV', srv_valid)

        self.assertEqual(srv_valid_content['values'][0]['priority'], 100)
        self.assertEqual(srv_invalid_content['values'][0]['priority'], 0)
        self.assertEqual(srv_invalid_content2['values'][0]['priority'], 11)
        self.assertEqual(srv_invalid_content3['values'][0]['priority'], 12)
        self.assertEqual(srv_invalid_content4['values'][0]['priority'], 13)

        self.assertEqual(srv_valid_content['values'][0]['weight'], 20)
        self.assertEqual(srv_invalid_content['values'][0]['weight'], 0)
        self.assertEqual(srv_invalid_content2['values'][0]['weight'], 0)
        self.assertEqual(srv_invalid_content3['values'][0]['weight'], 30)
        self.assertEqual(srv_invalid_content4['values'][0]['weight'], 40)

        self.assertEqual(srv_valid_content['values'][0]['port'], 5678)
        self.assertEqual(srv_invalid_content['values'][0]['port'], 0)
        self.assertEqual(srv_invalid_content2['values'][0]['port'], 0)
        self.assertEqual(srv_invalid_content3['values'][0]['port'], 0)
        self.assertEqual(srv_invalid_content4['values'][0]['port'], 1234)

        self.assertEqual(srv_valid_content['values'][0]['target'],
                         'foo-2.unit.tests.')
        self.assertEqual(srv_invalid_content['values'][0]['target'], '')
        self.assertEqual(srv_invalid_content2['values'][0]['target'], '')
        self.assertEqual(srv_invalid_content3['values'][0]['target'], '')
        self.assertEqual(srv_invalid_content4['values'][0]['target'], '')

    def test_apply(self):
        provider = EasyDNSProvider('test', 'token', 'apikey')

        resp = Mock()
        resp.json = Mock()
        provider._client._request = Mock(return_value=resp)

        domain_after_creation = {
            "tm": 1000000000,
            "data": [{
                "id": "12341001",
                "domain": "unit.tests",
                "host": "@",
                "ttl": "0",
                "prio": "0",
                "type": "SOA",
                "rdata": "dns1.easydns.com. zone.easydns.com. 2020010101"
                " 3600 600 604800 0",
                "geozone_id": "0",
                "last_mod": "2020-01-01 01:01:01"
            }, {
                "id": "12341002",
                "domain": "unit.tests",
                "host": "@",
                "ttl": "0",
                "prio": "0",
                "type": "NS",
                "rdata": "LOCAL.",
                "geozone_id": "0",
                "last_mod": "2020-01-01 01:01:01"
            }, {
                "id": "12341003",
                "domain": "unit.tests",
                "host": "@",
                "ttl": "0",
                "prio": "0",
                "type": "MX",
                "rdata": "LOCAL.",
                "geozone_id": "0",
                "last_mod": "2020-01-01 01:01:01"
            }],
            "count": 3,
            "total": 3,
            "start": 0,
            "max": 1000,
            "status": 200
        }

        # non-existent domain, create everything
        resp.json.side_effect = [
            EasyDNSClientNotFound,  # no zone in populate
            domain_after_creation
        ]
        plan = provider.plan(self.expected)

        # No root NS, no ignored, no excluded, no unsupported
        n = len(self.expected.records) - 7
        self.assertEquals(n, len(plan.changes))
        self.assertEquals(n, provider.apply(plan))
        self.assertFalse(plan.exists)

        self.assertEquals(23, provider._client._request.call_count)

        provider._client._request.reset_mock()

        # delete 1 and update 1
        provider._client.records = Mock(return_value=[
            {
                "id": "12342001",
                "domain": "unit.tests",
                "host": "www",
                "ttl": "300",
                "prio": "0",
                "type": "A",
                "rdata": "2.2.3.9",
                "geozone_id": "0",
                "last_mod": "2020-01-01 01:01:01"
            }, {
                "id": "12342002",
                "domain": "unit.tests",
                "host": "www",
                "ttl": "300",
                "prio": "0",
                "type": "A",
                "rdata": "2.2.3.8",
                "geozone_id": "0",
                "last_mod": "2020-01-01 01:01:01"
            }, {
                "id": "12342003",
                "domain": "unit.tests",
                "host": "test1",
                "ttl": "3600",
                "prio": "0",
                "type": "A",
                "rdata": "1.2.3.4",
                "geozone_id": "0",
                "last_mod": "2020-01-01 01:01:01"
            }
        ])

        # Domain exists, we don't care about return
        resp.json.side_effect = ['{}']

        wanted = Zone('unit.tests.', [])
        wanted.add_record(Record.new(wanted, 'test1', {
            "name": "test1",
            "ttl": 300,
            "type": "A",
            "value": "1.2.3.4",
        }))

        plan = provider.plan(wanted)
        self.assertTrue(plan.exists)
        self.assertEquals(2, len(plan.changes))
        self.assertEquals(2, provider.apply(plan))
        # recreate for update, and delete for the 2 parts of the other
        provider._client._request.assert_has_calls([
            call('PUT', '/zones/records/add/unit.tests/A', data={
                'rdata': '1.2.3.4',
                'name': 'test1',
                'ttl': 300,
                'type': 'A',
                'host': 'test1',
            }),
            call('DELETE', '/zones/records/unit.tests/12342001'),
            call('DELETE', '/zones/records/unit.tests/12342002'),
            call('DELETE', '/zones/records/unit.tests/12342003')
        ], any_order=True)
