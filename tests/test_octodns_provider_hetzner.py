#
#
#


from __future__ import absolute_import, division, print_function, \
    unicode_literals

from mock import Mock, call
from os.path import dirname, join
from requests import HTTPError
from requests_mock import ANY, mock as requests_mock
from six import text_type
from unittest import TestCase

from octodns.record import Record
from octodns.provider.hetzner import HetznerClientNotFound, \
    HetznerProvider
from octodns.provider.yaml import YamlProvider
from octodns.zone import Zone


class TestHetznerProvider(TestCase):
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
            base = provider._client.BASE_URL
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

    def test_apply(self):
        provider = HetznerProvider('test', 'token')

        resp = Mock()
        resp.json = Mock()
        provider._client._do = Mock(return_value=resp)

        domain_after_creation = {'zone': {
            'id': 'unit.tests',
            'name': 'unit.tests',
            'ttl': 3600,
        }}

        # non-existent domain, create everything
        resp.json.side_effect = [
            HetznerClientNotFound,  # no zone in populate
            HetznerClientNotFound,  # no zone during apply
            domain_after_creation,
        ]
        plan = provider.plan(self.expected)

        # No root NS, no ignored, no excluded, no unsupported
        n = len(self.expected.records) - 9
        self.assertEquals(n, len(plan.changes))
        self.assertEquals(n, provider.apply(plan))
        self.assertFalse(plan.exists)

        provider._client._do.assert_has_calls([
            # created the zone
            call('POST', '/zones', None, {
                'name': 'unit.tests',
                'ttl': None,
            }),
            # created all the records with their expected data
            call('POST', '/records', data={
                'name': '@',
                'ttl': 300,
                'type': 'A',
                'value': '1.2.3.4',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': '@',
                'ttl': 300,
                'type': 'A',
                'value': '1.2.3.5',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': '@',
                'ttl': 3600,
                'type': 'CAA',
                'value': '0 issue "ca.unit.tests"',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': '_imap._tcp',
                'ttl': 600,
                'type': 'SRV',
                'value': '0 0 0 .',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': '_pop3._tcp',
                'ttl': 600,
                'type': 'SRV',
                'value': '0 0 0 .',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': '_srv._tcp',
                'ttl': 600,
                'type': 'SRV',
                'value': '10 20 30 foo-1.unit.tests.',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': '_srv._tcp',
                'ttl': 600,
                'type': 'SRV',
                'value': '12 20 30 foo-2.unit.tests.',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': 'aaaa',
                'ttl': 600,
                'type': 'AAAA',
                'value': '2601:644:500:e210:62f8:1dff:feb8:947a',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': 'cname',
                'ttl': 300,
                'type': 'CNAME',
                'value': 'unit.tests.',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': 'included',
                'ttl': 3600,
                'type': 'CNAME',
                'value': 'unit.tests.',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': 'mx',
                'ttl': 300,
                'type': 'MX',
                'value': '10 smtp-4.unit.tests.',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': 'mx',
                'ttl': 300,
                'type': 'MX',
                'value': '20 smtp-2.unit.tests.',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': 'mx',
                'ttl': 300,
                'type': 'MX',
                'value': '30 smtp-3.unit.tests.',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': 'mx',
                'ttl': 300,
                'type': 'MX',
                'value': '40 smtp-1.unit.tests.',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': 'sub',
                'ttl': 3600,
                'type': 'NS',
                'value': '6.2.3.4.',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': 'sub',
                'ttl': 3600,
                'type': 'NS',
                'value': '7.2.3.4.',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': 'txt',
                'ttl': 600,
                'type': 'TXT',
                'value': 'Bah bah black sheep',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': 'txt',
                'ttl': 600,
                'type': 'TXT',
                'value': 'have you any wool.',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': 'txt',
                'ttl': 600,
                'type': 'TXT',
                'value': 'v=DKIM1;k=rsa;s=email;h=sha256;'
                         'p=A/kinda+of/long/string+with+numb3rs',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': 'www',
                'ttl': 300,
                'type': 'A',
                'value': '2.2.3.6',
                'zone_id': 'unit.tests',
            }),
            call('POST', '/records', data={
                'name': 'www.sub',
                'ttl': 300,
                'type': 'A',
                'value': '2.2.3.6',
                'zone_id': 'unit.tests',
            }),
        ])
        self.assertEquals(24, provider._client._do.call_count)

        provider._client._do.reset_mock()

        # delete 1 and update 1
        provider._client.zone_get = Mock(return_value={
            'id': 'unit.tests',
            'name': 'unit.tests',
            'ttl': 3600,
        })
        provider._client.zone_records_get = Mock(return_value=[
            {
                'type': 'A',
                'id': 'one',
                'created': '0000-00-00T00:00:00Z',
                'modified': '0000-00-00T00:00:00Z',
                'zone_id': 'unit.tests',
                'name': 'www',
                'value': '1.2.3.4',
                'ttl': 300,
            },
            {
                'type': 'A',
                'id': 'two',
                'created': '0000-00-00T00:00:00Z',
                'modified': '0000-00-00T00:00:00Z',
                'zone_id': 'unit.tests',
                'name': 'www',
                'value': '2.2.3.4',
                'ttl': 300,
            },
            {
                'type': 'A',
                'id': 'three',
                'created': '0000-00-00T00:00:00Z',
                'modified': '0000-00-00T00:00:00Z',
                'zone_id': 'unit.tests',
                'name': 'ttl',
                'value': '3.2.3.4',
                'ttl': 600,
            },
        ])

        # Domain exists, we don't care about return
        resp.json.side_effect = ['{}']

        wanted = Zone('unit.tests.', [])
        wanted.add_record(Record.new(wanted, 'ttl', {
            'ttl': 300,
            'type': 'A',
            'value': '3.2.3.4',
        }))

        plan = provider.plan(wanted)
        self.assertTrue(plan.exists)
        self.assertEquals(2, len(plan.changes))
        self.assertEquals(2, provider.apply(plan))
        # recreate for update, and delete for the 2 parts of the other
        provider._client._do.assert_has_calls([
            call('POST', '/records', data={
                'name': 'ttl',
                'ttl': 300,
                'type': 'A',
                'value': '3.2.3.4',
                'zone_id': 'unit.tests',
            }),
            call('DELETE', '/records/one'),
            call('DELETE', '/records/two'),
            call('DELETE', '/records/three'),
        ], any_order=True)
