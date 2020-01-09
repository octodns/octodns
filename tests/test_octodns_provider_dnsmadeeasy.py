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
from octodns.provider.dnsmadeeasy import DnsMadeEasyClientNotFound, \
    DnsMadeEasyProvider
from octodns.provider.yaml import YamlProvider
from octodns.zone import Zone

import json


class TestDnsMadeEasyProvider(TestCase):
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

    # Add some ALIAS records
    expected.add_record(Record.new(expected, '', {
        'ttl': 1800,
        'type': 'ALIAS',
        'value': 'aname.unit.tests.'
    }))

    expected.add_record(Record.new(expected, 'sub', {
        'ttl': 1800,
        'type': 'ALIAS',
        'value': 'aname.unit.tests.'
    }))

    for record in list(expected.records):
        if record.name == 'sub' and record._type == 'NS':
            expected._remove_record(record)
            break

    def test_populate(self):
        provider = DnsMadeEasyProvider('test', 'api', 'secret')

        # Bad auth
        with requests_mock() as mock:
            mock.get(ANY, status_code=401,
                     text='{"error": ["API key not found"]}')

            with self.assertRaises(Exception) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals('Unauthorized', text_type(ctx.exception))

        # Bad request
        with requests_mock() as mock:
            mock.get(ANY, status_code=400,
                     text='{"error": ["Rate limit exceeded"]}')

            with self.assertRaises(Exception) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals('\n  - Rate limit exceeded',
                              text_type(ctx.exception))

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
                     text='<html><head></head><body></body></html>')

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(set(), zone.records)

        # No diffs == no changes
        with requests_mock() as mock:
            base = 'https://api.dnsmadeeasy.com/V2.0/dns/managed'
            with open('tests/fixtures/dnsmadeeasy-domains.json') as fh:
                mock.get('{}{}'.format(base, '/'), text=fh.read())
            with open('tests/fixtures/dnsmadeeasy-records.json') as fh:
                mock.get('{}{}'.format(base, '/123123/records'),
                         text=fh.read())

                zone = Zone('unit.tests.', [])
                provider.populate(zone)
                self.assertEquals(15, len(zone.records))
                changes = self.expected.changes(zone, provider)
                self.assertEquals(1, len(changes))

        # 2nd populate makes no network calls/all from cache
        again = Zone('unit.tests.', [])
        provider.populate(again)
        self.assertEquals(15, len(again.records))

        # bust the cache
        del provider._zone_records[zone.name]

    def test_apply(self):
        # Create provider with sandbox enabled
        provider = DnsMadeEasyProvider('test', 'api', 'secret', True)

        resp = Mock()
        resp.json = Mock()
        provider._client._request = Mock(return_value=resp)

        with open('tests/fixtures/dnsmadeeasy-domains.json') as fh:
            domains = json.load(fh)

        # non-existent domain, create everything
        resp.json.side_effect = [
            DnsMadeEasyClientNotFound,  # no zone in populate
            DnsMadeEasyClientNotFound,  # no domain during apply
            domains
        ]
        plan = provider.plan(self.expected)

        # No root NS, no ignored, no excluded, no unsupported
        n = len(self.expected.records) - 5
        self.assertEquals(n, len(plan.changes))
        self.assertEquals(n, provider.apply(plan))

        provider._client._request.assert_has_calls([
            # created the domain
            call('POST', '/', data={'name': 'unit.tests'}),
            # get all domains to build the cache
            call('GET', '/'),
            # created at least some of the record with expected data
            call('POST', '/123123/records', data={
                'type': 'A',
                'name': '',
                'value': '1.2.3.4',
                'ttl': 300}),
            call('POST', '/123123/records', data={
                'type': 'A',
                'name': '',
                'value': '1.2.3.5',
                'ttl': 300}),
            call('POST', '/123123/records', data={
                'type': 'ANAME',
                'name': '',
                'value': 'aname.unit.tests.',
                'ttl': 1800}),
            call('POST', '/123123/records', data={
                'name': '',
                'value': 'ca.unit.tests',
                'issuerCritical': 0, 'caaType': 'issue',
                'ttl': 3600, 'type': 'CAA'}),
            call('POST', '/123123/records', data={
                'name': '_srv._tcp',
                'weight': 20,
                'value': 'foo-1.unit.tests.',
                'priority': 10,
                'ttl': 600,
                'type': 'SRV',
                'port': 30
            }),
        ])
        self.assertEquals(27, provider._client._request.call_count)

        provider._client._request.reset_mock()

        # delete 1 and update 1
        provider._client.records = Mock(return_value=[
            {
                'id': 11189897,
                'name': 'www',
                'value': '1.2.3.4',
                'ttl': 300,
                'type': 'A',
            },
            {
                'id': 11189898,
                'name': 'www',
                'value': '2.2.3.4',
                'ttl': 300,
                'type': 'A',
            },
            {
                'id': 11189899,
                'name': 'ttl',
                'value': '3.2.3.4',
                'ttl': 600,
                'type': 'A',
            }
        ])

        # Domain exists, we don't care about return
        resp.json.side_effect = ['{}']

        wanted = Zone('unit.tests.', [])
        wanted.add_record(Record.new(wanted, 'ttl', {
            'ttl': 300,
            'type': 'A',
            'value': '3.2.3.4'
        }))

        plan = provider.plan(wanted)
        self.assertEquals(2, len(plan.changes))
        self.assertEquals(2, provider.apply(plan))

        # recreate for update, and deletes for the 2 parts of the other
        provider._client._request.assert_has_calls([
            call('POST', '/123123/records', data={
                'value': '3.2.3.4',
                'type': 'A',
                'name': 'ttl',
                'ttl': 300
            }),
            call('DELETE', '/123123/records/11189899'),
            call('DELETE', '/123123/records/11189897'),
            call('DELETE', '/123123/records/11189898')
        ], any_order=True)
