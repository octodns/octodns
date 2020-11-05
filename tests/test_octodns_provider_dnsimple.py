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
from octodns.provider.dnsimple import DnsimpleClientNotFound, DnsimpleProvider
from octodns.provider.yaml import YamlProvider
from octodns.zone import Zone


class TestDnsimpleProvider(TestCase):
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

    def test_populate(self):

        # Sandbox
        provider = DnsimpleProvider('test', 'token', 42, 'true')
        self.assertTrue('sandbox' in provider._client.base)

        provider = DnsimpleProvider('test', 'token', 42)
        self.assertFalse('sandbox' in provider._client.base)

        # Bad auth
        with requests_mock() as mock:
            mock.get(ANY, status_code=401,
                     text='{"message": "Authentication failed"}')

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
                     text='{"message": "Domain `foo.bar` not found"}')

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(set(), zone.records)

        # No diffs == no changes
        with requests_mock() as mock:
            base = 'https://api.dnsimple.com/v2/42/zones/unit.tests/' \
                'records?page='
            with open('tests/fixtures/dnsimple-page-1.json') as fh:
                mock.get('{}{}'.format(base, 1), text=fh.read())
            with open('tests/fixtures/dnsimple-page-2.json') as fh:
                mock.get('{}{}'.format(base, 2), text=fh.read())

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(16, len(zone.records))
            changes = self.expected.changes(zone, provider)
            self.assertEquals(0, len(changes))

        # 2nd populate makes no network calls/all from cache
        again = Zone('unit.tests.', [])
        provider.populate(again)
        self.assertEquals(16, len(again.records))

        # bust the cache
        del provider._zone_records[zone.name]

        # test handling of invalid content
        with requests_mock() as mock:
            with open('tests/fixtures/dnsimple-invalid-content.json') as fh:
                mock.get(ANY, text=fh.read())

            zone = Zone('unit.tests.', [])
            provider.populate(zone, lenient=True)
            self.assertEquals(set([
                Record.new(zone, '', {
                    'ttl': 3600,
                    'type': 'SSHFP',
                    'values': []
                }, lenient=True),
                Record.new(zone, '_srv._tcp', {
                    'ttl': 600,
                    'type': 'SRV',
                    'values': []
                }, lenient=True),
                Record.new(zone, 'naptr', {
                    'ttl': 600,
                    'type': 'NAPTR',
                    'values': []
                }, lenient=True),
            ]), zone.records)

    def test_apply(self):
        provider = DnsimpleProvider('test', 'token', 42)

        resp = Mock()
        resp.json = Mock()
        provider._client._request = Mock(return_value=resp)

        # non-existent domain, create everything
        resp.json.side_effect = [
            DnsimpleClientNotFound,  # no zone in populate
            DnsimpleClientNotFound,  # no domain during apply
        ]
        plan = provider.plan(self.expected)

        # No root NS, no ignored, no excluded
        n = len(self.expected.records) - 4
        self.assertEquals(n, len(plan.changes))
        self.assertEquals(n, provider.apply(plan))
        self.assertFalse(plan.exists)

        provider._client._request.assert_has_calls([
            # created the domain
            call('POST', '/domains', data={'name': 'unit.tests'}),
            # created at least some of the record with expected data
            call('POST', '/zones/unit.tests/records', data={
                'content': '1.2.3.4',
                'type': 'A',
                'name': '',
                'ttl': 300}),
            call('POST', '/zones/unit.tests/records', data={
                'content': '1.2.3.5',
                'type': 'A',
                'name': '',
                'ttl': 300}),
            call('POST', '/zones/unit.tests/records', data={
                'content': '0 issue "ca.unit.tests"',
                'type': 'CAA',
                'name': '',
                'ttl': 3600}),
            call('POST', '/zones/unit.tests/records', data={
                'content': '1 1 7491973e5f8b39d5327cd4e08bc81b05f7710b49',
                'type': 'SSHFP',
                'name': '',
                'ttl': 3600}),
            call('POST', '/zones/unit.tests/records', data={
                'content': '1 1 bf6b6825d2977c511a475bbefb88aad54a92ac73',
                'type': 'SSHFP',
                'name': '',
                'ttl': 3600}),
            call('POST', '/zones/unit.tests/records', data={
                'content': '20 30 foo-1.unit.tests.',
                'priority': 10,
                'type': 'SRV',
                'name': '_srv._tcp',
                'ttl': 600
            }),
        ])
        # expected number of total calls
        self.assertEquals(28, provider._client._request.call_count)

        provider._client._request.reset_mock()

        # delete 1 and update 1
        provider._client.records = Mock(return_value=[
            {
                'id': 11189897,
                'name': 'www',
                'content': '1.2.3.4',
                'ttl': 300,
                'type': 'A',
            },
            {
                'id': 11189898,
                'name': 'www',
                'content': '2.2.3.4',
                'ttl': 300,
                'type': 'A',
            },
            {
                'id': 11189899,
                'name': 'ttl',
                'content': '3.2.3.4',
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
        self.assertTrue(plan.exists)
        self.assertEquals(2, len(plan.changes))
        self.assertEquals(2, provider.apply(plan))
        # recreate for update, and deletes for the 2 parts of the other
        provider._client._request.assert_has_calls([
            call('POST', '/zones/unit.tests/records', data={
                'content': '3.2.3.4',
                'type': 'A',
                'name': 'ttl',
                'ttl': 300
            }),
            call('DELETE', '/zones/unit.tests/records/11189899'),
            call('DELETE', '/zones/unit.tests/records/11189897'),
            call('DELETE', '/zones/unit.tests/records/11189898')
        ], any_order=True)
