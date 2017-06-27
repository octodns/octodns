#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import re
from json import loads, dumps
from os.path import dirname, join
from unittest import TestCase

from requests import HTTPError
from requests_mock import ANY, mock as requests_mock

from octodns.provider.rackspace import RackspaceProvider
from octodns.provider.yaml import YamlProvider
from octodns.record import Record
from octodns.zone import Zone

EMPTY_TEXT = '''
{
  "totalEntries" : 6,
  "records" : []
}
'''

with open('./tests/fixtures/rackspace-auth-response.json') as fh:
    AUTH_RESPONSE = fh.read()

with open('./tests/fixtures/rackspace-list-domains-response.json') as fh:
    LIST_DOMAINS_RESPONSE = fh.read()

with open('./tests/fixtures/rackspace-sample-recordset-page1.json') as fh:
    RECORDS_PAGE_1 = fh.read()

with open('./tests/fixtures/rackspace-sample-recordset-page2.json') as fh:
    RECORDS_PAGE_2 = fh.read()

def load_provider():
    with requests_mock() as mock:
        mock.post(ANY, status_code=200, text=AUTH_RESPONSE)
        return RackspaceProvider('test', 'api-key')


class TestRackspaceSource(TestCase):

    def test_provider(self):
        provider = load_provider()

        # Bad auth
        with requests_mock() as mock:
            mock.get(ANY, status_code=401, text='Unauthorized')

            with self.assertRaises(Exception) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertTrue('unauthorized' in ctx.exception.message)

        # General error
        with requests_mock() as mock:
            mock.get(ANY, status_code=502, text='Things caught fire')

            with self.assertRaises(HTTPError) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals(502, ctx.exception.response.status_code)

        # Non-existant zone doesn't populate anything
        with requests_mock() as mock:
            mock.get(ANY, status_code=422,
                     json={'error': "Could not find domain 'unit.tests.'"})

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(set(), zone.records)

        # The rest of this is messy/complicated b/c it's dealing with mocking

        expected = Zone('unit.tests.', [])
        source = YamlProvider('test', join(dirname(__file__), 'config'))
        source.populate(expected)
        expected_n = len(expected.records) - 1
        self.assertEquals(14, expected_n)

        # No diffs == no changes
        with requests_mock() as mock:
            mock.get(re.compile('domains$'), status_code=200, text=LIST_DOMAINS_RESPONSE)
            mock.get(re.compile('records'), status_code=200, text=RECORDS_PAGE_1)
            mock.get(re.compile('records.*offset=3'), status_code=200, text=RECORDS_PAGE_2)

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(14, len(zone.records))
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
            # post 201, is reponse to the create with data
            mock.patch(ANY, status_code=201, text=assert_rrsets_callback)

            plan = provider.plan(expected)
            self.assertEquals(expected_n, len(plan.changes))
            self.assertEquals(expected_n, provider.apply(plan))

        # Non-existent zone -> creates for every record in expected
        # OMG this is fucking ugly, probably better to ditch requests_mocks and
        # just mock things for real as it doesn't seem to provide a way to get
        # at the request params or verify that things were called from what I
        # can tell
        not_found = {'error': "Could not find domain 'unit.tests.'"}
        with requests_mock() as mock:
            # get 422's, unknown zone
            mock.get(ANY, status_code=422, text='')
            # patch 422's, unknown zone
            mock.patch(ANY, status_code=422, text=dumps(not_found))
            # post 201, is reponse to the create with data
            mock.post(ANY, status_code=201, text=assert_rrsets_callback)

            plan = provider.plan(expected)
            self.assertEquals(expected_n, len(plan.changes))
            self.assertEquals(expected_n, provider.apply(plan))

        with requests_mock() as mock:
            # get 422's, unknown zone
            mock.get(ANY, status_code=422, text='')
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
            mock.get(ANY, status_code=422, text='')
            # patch 500's, things just blew up
            mock.patch(ANY, status_code=500, text='')

            with self.assertRaises(HTTPError):
                plan = provider.plan(expected)
                provider.apply(plan)

        with requests_mock() as mock:
            # get 422's, unknown zone
            mock.get(ANY, status_code=422, text='')
            # patch 500's, things just blew up
            mock.patch(ANY, status_code=422, text=dumps(not_found))
            # post 422's, something wrong with create
            mock.post(ANY, status_code=422, text='Hello Word!')

            with self.assertRaises(HTTPError):
                plan = provider.plan(expected)
                provider.apply(plan)

    def test_small_change(self):
        provider = load_provider()

        expected = Zone('unit.tests.', [])
        source = YamlProvider('test', join(dirname(__file__), 'config'))
        source.populate(expected)
        self.assertEquals(15, len(expected.records))

        # A small change to a single record
        with requests_mock() as mock:
            mock.get(ANY, status_code=200, text=FULL_TEXT)

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
        provider = load_provider()

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

            unrelated_record = Record.new(expected, '', {
                'type': 'A',
                'ttl': 60,
                'value': '1.2.3.4'
            })
            expected.add_record(unrelated_record)
            plan = provider.plan(expected)
            self.assertFalse(plan)
            # remove it now that we don't need the unrelated change any longer
            expected.records.remove(unrelated_record)

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
