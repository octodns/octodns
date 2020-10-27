#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from json import loads, dumps
from os.path import dirname, join
from requests import HTTPError
from requests_mock import ANY, mock as requests_mock
from six import text_type
from unittest import TestCase

from octodns.record import Record
from octodns.provider.powerdns import PowerDnsProvider
from octodns.provider.yaml import YamlProvider
from octodns.zone import Zone

EMPTY_TEXT = '''
{
    "account": "",
    "dnssec": false,
    "id": "xunit.tests.",
    "kind": "Master",
    "last_check": 0,
    "masters": [],
    "name": "xunit.tests.",
    "notified_serial": 0,
    "rrsets": [],
    "serial": 2017012801,
    "soa_edit": "",
    "soa_edit_api": "INCEPTION-INCREMENT",
    "url": "api/v1/servers/localhost/zones/xunit.tests."
}
'''

with open('./tests/fixtures/powerdns-full-data.json') as fh:
    FULL_TEXT = fh.read()


class TestPowerDnsProvider(TestCase):

    def test_provider_version_detection(self):
        provider = PowerDnsProvider('test', 'non.existent', 'api-key',
                                    nameserver_values=['8.8.8.8.',
                                                       '9.9.9.9.'])
        # Bad auth
        with requests_mock() as mock:
            mock.get(ANY, status_code=401, text='Unauthorized')

            with self.assertRaises(Exception) as ctx:
                provider.powerdns_version
            self.assertTrue('unauthorized' in text_type(ctx.exception))

        # Api not found
        with requests_mock() as mock:
            mock.get(ANY, status_code=404, text='Not Found')

            with self.assertRaises(Exception) as ctx:
                provider.powerdns_version
            self.assertTrue('404' in text_type(ctx.exception))

        # Test version detection
        with requests_mock() as mock:
            mock.get('http://non.existent:8081/api/v1/servers/localhost',
                     status_code=200, json={'version': "4.1.10"})
            self.assertEquals(provider.powerdns_version, [4, 1, 10])

        # Test version detection for second time (should stay at 4.1.10)
        with requests_mock() as mock:
            mock.get('http://non.existent:8081/api/v1/servers/localhost',
                     status_code=200, json={'version': "4.2.0"})
            self.assertEquals(provider.powerdns_version, [4, 1, 10])

        # Test version detection
        with requests_mock() as mock:
            mock.get('http://non.existent:8081/api/v1/servers/localhost',
                     status_code=200, json={'version': "4.2.0"})

            # Reset version, so detection will try again
            provider._powerdns_version = None
            self.assertNotEquals(provider.powerdns_version, [4, 1, 10])

    def test_provider_version_config(self):
        provider = PowerDnsProvider('test', 'non.existent', 'api-key',
                                    nameserver_values=['8.8.8.8.',
                                                       '9.9.9.9.'])

        # Test version 4.1.0
        provider._powerdns_version = None
        with requests_mock() as mock:
            mock.get('http://non.existent:8081/api/v1/servers/localhost',
                     status_code=200, json={'version': "4.1.10"})
            self.assertEquals(provider.soa_edit_api, 'INCEPTION-INCREMENT')
            self.assertFalse(
                provider.check_status_not_found,
                'check_status_not_found should be false '
                'for version 4.1.x and below')

        # Test version 4.2.0
        provider._powerdns_version = None
        with requests_mock() as mock:
            mock.get('http://non.existent:8081/api/v1/servers/localhost',
                     status_code=200, json={'version': "4.2.0"})
            self.assertEquals(provider.soa_edit_api, 'INCEPTION-INCREMENT')
            self.assertTrue(
                provider.check_status_not_found,
                'check_status_not_found should be true for version 4.2.x')

        # Test version 4.3.0
        provider._powerdns_version = None
        with requests_mock() as mock:
            mock.get('http://non.existent:8081/api/v1/servers/localhost',
                     status_code=200, json={'version': "4.3.0"})
            self.assertEquals(provider.soa_edit_api, 'DEFAULT')
            self.assertTrue(
                provider.check_status_not_found,
                'check_status_not_found should be true for version 4.3.x')

    def test_provider(self):
        provider = PowerDnsProvider('test', 'non.existent', 'api-key',
                                    nameserver_values=['8.8.8.8.',
                                                       '9.9.9.9.'])

        # Test version detection
        with requests_mock() as mock:
            mock.get('http://non.existent:8081/api/v1/servers/localhost',
                     status_code=200, json={'version': "4.1.10"})
            self.assertEquals(provider.powerdns_version, [4, 1, 10])

        # Bad auth
        with requests_mock() as mock:
            mock.get(ANY, status_code=401, text='Unauthorized')

            with self.assertRaises(Exception) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertTrue('unauthorized' in text_type(ctx.exception))

        # General error
        with requests_mock() as mock:
            mock.get(ANY, status_code=502, text='Things caught fire')

            with self.assertRaises(HTTPError) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals(502, ctx.exception.response.status_code)

        # Non-existent zone in PowerDNS <4.3.0 doesn't populate anything
        with requests_mock() as mock:
            mock.get(ANY, status_code=422,
                     json={'error': "Could not find domain 'unit.tests.'"})
            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(set(), zone.records)

        # Non-existent zone in PowerDNS >=4.2.0 doesn't populate anything

        provider._powerdns_version = [4, 2, 0]
        with requests_mock() as mock:
            mock.get(ANY, status_code=404, text='Not Found')
            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(set(), zone.records)

        provider._powerdns_version = [4, 1, 0]

        # The rest of this is messy/complicated b/c it's dealing with mocking

        expected = Zone('unit.tests.', [])
        source = YamlProvider('test', join(dirname(__file__), 'config'))
        source.populate(expected)
        expected_n = len(expected.records) - 3
        self.assertEquals(16, expected_n)

        # No diffs == no changes
        with requests_mock() as mock:
            mock.get(ANY, status_code=200, text=FULL_TEXT)

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(16, len(zone.records))
            changes = expected.changes(zone, provider)
            self.assertEquals(0, len(changes))

        # Used in a minute
        def assert_rrsets_callback(request, context):
            data = loads(request.body)
            self.assertEquals(expected_n, len(data['rrsets']))
            return ''

        # No existing records -> creates for every record in expected
        with requests_mock() as mock:
            mock.get(ANY, status_code=200, text=EMPTY_TEXT)
            # post 201, is response to the create with data
            mock.patch(ANY, status_code=201, text=assert_rrsets_callback)

            plan = provider.plan(expected)
            self.assertEquals(expected_n, len(plan.changes))
            self.assertEquals(expected_n, provider.apply(plan))
            self.assertTrue(plan.exists)

        # Non-existent zone -> creates for every record in expected
        # OMG this is fucking ugly, probably better to ditch requests_mocks and
        # just mock things for real as it doesn't seem to provide a way to get
        # at the request params or verify that things were called from what I
        # can tell
        not_found = {'error': "Could not find domain 'unit.tests.'"}
        with requests_mock() as mock:
            # get 422's, unknown zone
            mock.get(ANY, status_code=422, text=dumps(not_found))
            # patch 422's, unknown zone
            mock.patch(ANY, status_code=422, text=dumps(not_found))
            # post 201, is response to the create with data
            mock.post(ANY, status_code=201, text=assert_rrsets_callback)

            plan = provider.plan(expected)
            self.assertEquals(expected_n, len(plan.changes))
            self.assertEquals(expected_n, provider.apply(plan))
            self.assertFalse(plan.exists)

        provider._powerdns_version = [4, 2, 0]
        with requests_mock() as mock:
            # get 404's, unknown zone
            mock.get(ANY, status_code=404, text='')
            # patch 404's, unknown zone
            mock.patch(ANY, status_code=404, text=dumps(not_found))
            # post 201, is response to the create with data
            mock.post(ANY, status_code=201, text=assert_rrsets_callback)

            plan = provider.plan(expected)
            self.assertEquals(expected_n, len(plan.changes))
            self.assertEquals(expected_n, provider.apply(plan))
            self.assertFalse(plan.exists)

        provider._powerdns_version = [4, 1, 0]
        with requests_mock() as mock:
            # get 422's, unknown zone
            mock.get(ANY, status_code=422, text=dumps(not_found))
            # patch 422's,
            data = {'error': "Key 'name' not present or not a String"}
            mock.patch(ANY, status_code=422, text=dumps(data))

            with self.assertRaises(HTTPError) as ctx:
                plan = provider.plan(expected)
                provider.apply(plan)
            response = ctx.exception.response
            self.assertEquals(422, response.status_code)
            self.assertTrue('error' in response.json())

        with requests_mock() as mock:
            # get 422's, unknown zone
            mock.get(ANY, status_code=422, text=dumps(not_found))
            # patch 500's, things just blew up
            mock.patch(ANY, status_code=500, text='')

            with self.assertRaises(HTTPError):
                plan = provider.plan(expected)
                provider.apply(plan)

        with requests_mock() as mock:
            # get 422's, unknown zone
            mock.get(ANY, status_code=422, text=dumps(not_found))
            # patch 500's, things just blew up
            mock.patch(ANY, status_code=422, text=dumps(not_found))
            # post 422's, something wrong with create
            mock.post(ANY, status_code=422, text='Hello Word!')

            with self.assertRaises(HTTPError):
                plan = provider.plan(expected)
                provider.apply(plan)

    def test_small_change(self):
        provider = PowerDnsProvider('test', 'non.existent', 'api-key')

        expected = Zone('unit.tests.', [])
        source = YamlProvider('test', join(dirname(__file__), 'config'))
        source.populate(expected)
        self.assertEquals(19, len(expected.records))

        # A small change to a single record
        with requests_mock() as mock:
            mock.get(ANY, status_code=200, text=FULL_TEXT)
            mock.get('http://non.existent:8081/api/v1/servers/localhost',
                     status_code=200, json={'version': '4.1.0'})

            missing = Zone(expected.name, [])
            # Find and delete the SPF record
            for record in expected.records:
                if record._type != 'SPF':
                    missing.add_record(record)

            def assert_delete_callback(request, context):
                self.assertEquals({
                    'rrsets': [{
                        'records': [
                            {'content': '"v=spf1 ip4:192.168.0.1/16-all"',
                             'disabled': False}
                        ],
                        'changetype': 'DELETE',
                        'type': 'SPF',
                        'name': 'spf.unit.tests.',
                        'ttl': 600
                    }]
                }, loads(request.body))
                return ''

            mock.patch(ANY, status_code=201, text=assert_delete_callback)

            plan = provider.plan(missing)
            self.assertEquals(1, len(plan.changes))
            self.assertEquals(1, provider.apply(plan))

    def test_existing_nameservers(self):
        ns_values = ['8.8.8.8.', '9.9.9.9.']
        provider = PowerDnsProvider('test', 'non.existent', 'api-key',
                                    nameserver_values=ns_values)

        expected = Zone('unit.tests.', [])
        ns_record = Record.new(expected, '', {
            'type': 'NS',
            'ttl': 600,
            'values': ns_values
        })
        expected.add_record(ns_record)

        # no changes
        with requests_mock() as mock:
            data = {
                'rrsets': [{
                    'comments': [],
                    'name': 'unit.tests.',
                    'records': [
                        {
                            'content': '8.8.8.8.',
                            'disabled': False
                        },
                        {
                            'content': '9.9.9.9.',
                            'disabled': False
                        }
                    ],
                    'ttl': 600,
                    'type': 'NS'
                }, {
                    'comments': [],
                    'name': 'unit.tests.',
                    'records': [{
                        'content': '1.2.3.4',
                        'disabled': False,
                    }],
                    'ttl': 60,
                    'type': 'A'
                }]
            }
            mock.get(ANY, status_code=200, json=data)
            mock.get('http://non.existent:8081/api/v1/servers/localhost',
                     status_code=200, json={'version': '4.1.0'})

            unrelated_record = Record.new(expected, '', {
                'type': 'A',
                'ttl': 60,
                'value': '1.2.3.4'
            })
            expected.add_record(unrelated_record)
            plan = provider.plan(expected)
            self.assertFalse(plan)
            # remove it now that we don't need the unrelated change any longer
            expected._remove_record(unrelated_record)

        # ttl diff
        with requests_mock() as mock:
            data = {
                'rrsets': [{
                    'comments': [],
                    'name': 'unit.tests.',
                    'records': [
                        {
                            'content': '8.8.8.8.',
                            'disabled': False
                        },
                        {
                            'content': '9.9.9.9.',
                            'disabled': False
                        },
                    ],
                    'ttl': 3600,
                    'type': 'NS'
                }]
            }
            mock.get(ANY, status_code=200, json=data)
            mock.get('http://non.existent:8081/api/v1/servers/localhost',
                     status_code=200, json={'version': '4.1.0'})

            plan = provider.plan(expected)
            self.assertEquals(1, len(plan.changes))

        # create
        with requests_mock() as mock:
            data = {
                'rrsets': []
            }
            mock.get(ANY, status_code=200, json=data)

            plan = provider.plan(expected)
            self.assertEquals(1, len(plan.changes))
