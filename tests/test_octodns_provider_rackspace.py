#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import json
import re
from os.path import dirname, join
from unittest import TestCase
from urlparse import urlparse

from requests import HTTPError
from requests_mock import ANY, mock as requests_mock

from octodns.provider.rackspace import RackspaceProvider
from octodns.provider.yaml import YamlProvider
from octodns.record import Record
from octodns.zone import Zone

from pprint import pprint

EMPTY_TEXT = '''
{
  "totalEntries" : 0,
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

with open('./tests/fixtures/rackspace-sample-recordset-existing-nameservers.json') as fh:
    RECORDS_EXISTING_NAMESERVERS = fh.read()


class TestRackspaceProvider(TestCase):
    def setUp(self):
        self.maxDiff = 1000
        with requests_mock() as mock:
            mock.post(ANY, status_code=200, text=AUTH_RESPONSE)
            self.provider = RackspaceProvider(id, 'test', 'api-key')
            self.assertTrue(mock.called_once)

    def test_bad_auth(self):
        with requests_mock() as mock:
            mock.get(ANY, status_code=401, text='Unauthorized')

            with self.assertRaises(Exception) as ctx:
                zone = Zone('unit.tests.', [])
                self.provider.populate(zone)
            self.assertTrue('unauthorized' in ctx.exception.message)
            self.assertTrue(mock.called_once)

    def test_server_error(self):
        with requests_mock() as mock:
            mock.get(ANY, status_code=502, text='Things caught fire')

            with self.assertRaises(HTTPError) as ctx:
                zone = Zone('unit.tests.', [])
                self.provider.populate(zone)
            self.assertEquals(502, ctx.exception.response.status_code)
            self.assertTrue(mock.called_once)

    def test_nonexistent_zone(self):
        # Non-existent zone doesn't populate anything
        with requests_mock() as mock:
            mock.get(ANY, status_code=404,
                     json={'error': "Could not find domain 'unit.tests.'"})

            zone = Zone('unit.tests.', [])
            self.provider.populate(zone)
            self.assertEquals(set(), zone.records)
            self.assertTrue(mock.called_once)

    def test_multipage_populate(self):
        with requests_mock() as mock:
            mock.get(re.compile('domains$'), status_code=200, text=LIST_DOMAINS_RESPONSE)
            mock.get(re.compile('records'), status_code=200, text=RECORDS_PAGE_1)
            mock.get(re.compile('records.*offset=3'), status_code=200, text=RECORDS_PAGE_2)

            zone = Zone('unit.tests.', [])
            self.provider.populate(zone)
            self.assertEquals(5, len(zone.records))

    def _load_full_config(self):
        expected = Zone('unit.tests.', [])
        source = YamlProvider('test', join(dirname(__file__), 'config'))
        source.populate(expected)
        self.assertEquals(15, len(expected.records))
        return expected

    def test_changes_are_formatted_correctly(self):
        expected = self._load_full_config()

        # No diffs == no changes
        with requests_mock() as mock:
            mock.get(re.compile('domains$'), status_code=200, text=LIST_DOMAINS_RESPONSE)
            mock.get(re.compile('records'), status_code=200, text=RECORDS_PAGE_1)
            mock.get(re.compile('records.*offset=3'), status_code=200, text=RECORDS_PAGE_2)

            zone = Zone('unit.tests.', [])
            self.provider.populate(zone)
            changes = expected.changes(zone, self.provider)
            self.assertEquals(18, len(changes))

    def test_plan_disappearing_ns_records(self):
        expected = Zone('unit.tests.', [])
        expected.add_record(Record.new(expected, '', {
            'type': 'NS',
            'ttl': 600,
            'values': ['8.8.8.8.', '9.9.9.9.']
        }))
        expected.add_record(Record.new(expected, 'sub', {
            'type': 'NS',
            'ttl': 600,
            'values': ['8.8.8.8.', '9.9.9.9.']
        }))
        with requests_mock() as mock:
            mock.get(re.compile('domains$'), status_code=200, text=LIST_DOMAINS_RESPONSE)
            mock.get(re.compile('records'), status_code=200, text=EMPTY_TEXT)

            plan = self.provider.plan(expected)
            self.assertTrue(mock.called)

            # OctoDNS does not propagate top-level NS records.
            self.assertEquals(1, len(plan.changes))

    def test_fqdn_a_record(self):
        expected = Zone('example.com.', [])
        # expected.add_record(Record.new(expected, 'foo', '1.2.3.4'))

        with requests_mock() as list_mock:
            list_mock.get(re.compile('domains$'), status_code=200, text=LIST_DOMAINS_RESPONSE)
            list_mock.get(re.compile('records'), status_code=200, json={'records': [
                {'type': 'A',
                 'name': 'foo.example.com',
                 'id': 'A-111111',
                 'data': '1.2.3.4',
                 'ttl': 300}]})
            plan = self.provider.plan(expected)
            self.assertTrue(list_mock.called)
            self.assertEqual(1, len(plan.changes))
            self.assertTrue(plan.changes[0].existing.fqdn == 'foo.example.com.')

        with requests_mock() as mock:
            def _assert_deleting(request, context):
                parts = urlparse(request.url)
                self.assertEqual('id=A-111111', parts.query)
            mock.get(re.compile('domains$'), status_code=200, text=LIST_DOMAINS_RESPONSE)
            mock.delete(re.compile('domains/.*/records?.*'), status_code=202,
                        text=_assert_deleting)
            self.provider.apply(plan)
            self.assertTrue(mock.called)

    def _test_apply_with_data(self, data):
        expected = Zone('unit.tests.', [])
        for record in data.OtherRecords:
            expected.add_record(Record.new(expected, record['subdomain'], record['data']))

        with requests_mock() as list_mock:
            list_mock.get(re.compile('domains$'), status_code=200, text=LIST_DOMAINS_RESPONSE)
            list_mock.get(re.compile('records'), status_code=200, json=data.OwnRecords)
            plan = self.provider.plan(expected)
            self.assertTrue(list_mock.called)
            if not data.ExpectChanges:
                self.assertFalse(plan)
                return

        with requests_mock() as mock:
            called = set()

            def make_assert_sending_right_body(expected):
                def _assert_sending_right_body(request, _context):
                    called.add(request.method)
                    if request.method != 'DELETE':
                        self.assertEqual(request.headers['content-type'], 'application/json')
                        self.assertDictEqual(expected, json.loads(request.body))
                    else:
                        parts = urlparse(request.url)
                        self.assertEqual(expected, parts.query)
                    return ''
                return _assert_sending_right_body

            mock.get(re.compile('domains$'), status_code=200, text=LIST_DOMAINS_RESPONSE)
            mock.post(re.compile('domains/.*/records$'), status_code=202,
                      text=make_assert_sending_right_body(data.ExpectedAdditions))
            mock.delete(re.compile('domains/.*/records?.*'), status_code=202,
                        text=make_assert_sending_right_body(data.ExpectedDeletions))
            mock.put(re.compile('domains/.*/records$'), status_code=202,
                     text=make_assert_sending_right_body(data.ExpectedUpdates))

            self.provider.apply(plan)
            self.assertTrue(data.ExpectedAdditions is None or "POST" in called)
            self.assertTrue(data.ExpectedDeletions is None or "DELETE" in called)
            self.assertTrue(data.ExpectedUpdates is None or "PUT" in called)

    def test_apply_no_change_empty(self):
        class TestData(object):
            OtherRecords = []
            OwnRecords = {
                "totalEntries": 0,
                "records": []
            }
            ExpectChanges = False
            ExpectedAdditions = None
            ExpectedDeletions = None
            ExpectedUpdates = None
        return self._test_apply_with_data(TestData)

    def test_apply_no_change_a_records(self):
        class TestData(object):
            OtherRecords = [
                {
                    "subdomain": '',
                    "data": {
                        'type': 'A',
                        'ttl': 300,
                        'values': ['1.2.3.4', '1.2.3.5', '1.2.3.6']
                    }
                }
            ]
            OwnRecords = {
                "totalEntries": 3,
                "records": [{
                    "name": "unit.tests.",
                    "id": "A-111111",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "unit.tests.",
                    "id": "A-222222",
                    "type": "A",
                    "data": "1.2.3.5",
                    "ttl": 300
                }, {
                    "name": "unit.tests.",
                    "id": "A-333333",
                    "type": "A",
                    "data": "1.2.3.6",
                    "ttl": 300
                }]
            }
            ExpectChanges = False
            ExpectedAdditions = None
            ExpectedDeletions = None
            ExpectedUpdates = None
        return self._test_apply_with_data(TestData)

    def test_apply_no_change_a_records_cross_zone(self):
        class TestData(object):
            OtherRecords = [
                {
                    "subdomain": 'foo',
                    "data": {
                        'type': 'A',
                        'ttl': 300,
                        'value': '1.2.3.4'
                    }
                },
                {
                    "subdomain": 'bar',
                    "data": {
                        'type': 'A',
                        'ttl': 300,
                        'value': '1.2.3.4'
                    }
                }
            ]
            OwnRecords = {
                "totalEntries": 3,
                "records": [{
                    "name": "foo.unit.tests.",
                    "id": "A-111111",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "bar.unit.tests.",
                    "id": "A-222222",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }]
            }
            ExpectChanges = False
            ExpectedAdditions = None
            ExpectedDeletions = None
            ExpectedUpdates = None
        return self._test_apply_with_data(TestData)

    def test_apply_one_addition(self):
        class TestData(object):
            OtherRecords = [
                {
                    "subdomain": '',
                    "data": {
                        'type': 'A',
                        'ttl': 300,
                        'value': '1.2.3.4'
                    }
                },
                {
                    "subdomain": 'foo',
                    "data": {
                        'type': 'NS',
                        'ttl': 300,
                        'value': 'ns.example.com.'
                    }
                }
            ]
            OwnRecords = {
                "totalEntries": 0,
                "records": []
            }
            ExpectChanges = True
            ExpectedAdditions = {
                "records": [{
                    "name": "unit.tests.",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests.",
                    "type": "NS",
                    "data": "ns.example.com",
                    "ttl": 300
                }]
            }
            ExpectedDeletions = None
            ExpectedUpdates = None
        return self._test_apply_with_data(TestData)

    def test_apply_multiple_additions_exploding(self):
        class TestData(object):
            OtherRecords = [
                {
                    "subdomain": '',
                    "data": {
                        'type': 'A',
                        'ttl': 300,
                        'values': ['1.2.3.4', '1.2.3.5', '1.2.3.6']
                    }
                },
                {
                    "subdomain": 'foo',
                    "data": {
                        'type': 'NS',
                        'ttl': 300,
                        'values': ['ns1.example.com.', 'ns2.example.com.']
                    }
                }
            ]
            OwnRecords = {
                "totalEntries": 0,
                "records": []
            }
            ExpectChanges = True
            ExpectedAdditions = {
                "records": [{
                    "name": "unit.tests.",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "unit.tests.",
                    "type": "A",
                    "data": "1.2.3.5",
                    "ttl": 300
                }, {
                    "name": "unit.tests.",
                    "type": "A",
                    "data": "1.2.3.6",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests.",
                    "type": "NS",
                    "data": "ns1.example.com",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests.",
                    "type": "NS",
                    "data": "ns2.example.com",
                    "ttl": 300
                }]
            }
            ExpectedDeletions = None
            ExpectedUpdates = None
        return self._test_apply_with_data(TestData)

    def test_apply_multiple_additions_namespaced(self):
        class TestData(object):
            OtherRecords = [{
                    "subdomain": 'foo',
                    "data": {
                        'type': 'A',
                        'ttl': 300,
                        'value': '1.2.3.4'
                    }
                }, {
                    "subdomain": 'bar',
                    "data": {
                        'type': 'A',
                        'ttl': 300,
                        'value': '1.2.3.4'
                    }
                },
                {
                    "subdomain": 'foo',
                    "data": {
                        'type': 'NS',
                        'ttl': 300,
                        'value': 'ns.example.com.'
                    }
                }]
            OwnRecords = {
                "totalEntries": 0,
                "records": []
            }
            ExpectChanges = True
            ExpectedAdditions = {
                "records": [{
                    "name": "bar.unit.tests.",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests.",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests.",
                    "type": "NS",
                    "data": "ns.example.com",
                    "ttl": 300
                }]
            }
            ExpectedDeletions = None
            ExpectedUpdates = None
        return self._test_apply_with_data(TestData)

    def test_apply_single_deletion(self):
        class TestData(object):
            OtherRecords = []
            OwnRecords = {
                "totalEntries": 1,
                "records": [{
                    "name": "unit.tests.",
                    "id": "A-111111",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests.",
                    "id": "NS-111111",
                    "type": "NS",
                    "data": "ns.example.com",
                    "ttl": 300
                }]
            }
            ExpectChanges = True
            ExpectedAdditions = None
            ExpectedDeletions = "id=A-111111&id=NS-111111"
            ExpectedUpdates = None
        return self._test_apply_with_data(TestData)

    def test_apply_multiple_deletions(self):
        class TestData(object):
            OtherRecords = [
                {
                    "subdomain": '',
                    "data": {
                        'type': 'A',
                        'ttl': 300,
                        'value': '1.2.3.5'
                    }
                }
            ]
            OwnRecords = {
                "totalEntries": 3,
                "records": [{
                    "name": "unit.tests.",
                    "id": "A-111111",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "unit.tests.",
                    "id": "A-222222",
                    "type": "A",
                    "data": "1.2.3.5",
                    "ttl": 300
                }, {
                    "name": "unit.tests.",
                    "id": "A-333333",
                    "type": "A",
                    "data": "1.2.3.6",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests.",
                    "id": "NS-111111",
                    "type": "NS",
                    "data": "ns.example.com",
                    "ttl": 300
                }]
            }
            ExpectChanges = True
            ExpectedAdditions = None
            ExpectedDeletions = "id=A-111111&id=A-333333&id=NS-111111"
            ExpectedUpdates = {
                "records": [{
                    "name": "unit.tests.",
                    "id": "A-222222",
                    "data": "1.2.3.5",
                    "ttl": 300
                }]
            }
        return self._test_apply_with_data(TestData)

    def test_apply_multiple_deletions_cross_zone(self):
        class TestData(object):
            OtherRecords = [
                {
                    "subdomain": '',
                    "data": {
                        'type': 'A',
                        'ttl': 300,
                        'value': '1.2.3.4'
                    }
                }
            ]
            OwnRecords = {
                "totalEntries": 3,
                "records": [{
                    "name": "unit.tests.",
                    "id": "A-111111",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests.",
                    "id": "A-222222",
                    "type": "A",
                    "data": "1.2.3.5",
                    "ttl": 300
                }, {
                    "name": "bar.unit.tests.",
                    "id": "A-333333",
                    "type": "A",
                    "data": "1.2.3.6",
                    "ttl": 300
                }]
            }
            ExpectChanges = True
            ExpectedAdditions = None
            ExpectedDeletions = "id=A-222222&id=A-333333"
            ExpectedUpdates = None
        return self._test_apply_with_data(TestData)

    def test_apply_single_update(self):
        class TestData(object):
            OtherRecords = [
                {
                    "subdomain": '',
                    "data": {
                        'type': 'A',
                        'ttl': 3600,
                        'value': '1.2.3.4'
                    }
                }
            ]
            OwnRecords = {
                "totalEntries": 1,
                "records": [{
                    "name": "unit.tests.",
                    "id": "A-111111",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }]
            }
            ExpectChanges = True
            ExpectedAdditions = None
            ExpectedDeletions = None
            ExpectedUpdates = {
                "records": [{
                    "name": "unit.tests.",
                    "id": "A-111111",
                    "data": "1.2.3.4",
                    "ttl": 3600
                }]
            }
        return self._test_apply_with_data(TestData)

    def test_apply_multiple_updates(self):
        class TestData(object):
            OtherRecords = [
                {
                    "subdomain": '',
                    "data": {
                        'type': 'A',
                        'ttl': 3600,
                        'values': ['1.2.3.4', '1.2.3.5', '1.2.3.6']
                    }
                }
            ]
            OwnRecords = {
                "totalEntries": 3,
                "records": [{
                    "name": "unit.tests.",
                    "id": "A-111111",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "unit.tests.",
                    "id": "A-222222",
                    "type": "A",
                    "data": "1.2.3.5",
                    "ttl": 300
                }, {
                    "name": "unit.tests.",
                    "id": "A-333333",
                    "type": "A",
                    "data": "1.2.3.6",
                    "ttl": 300
                }]
            }
            ExpectChanges = True
            ExpectedAdditions = None
            ExpectedDeletions = None
            ExpectedUpdates = {
                "records": [{
                    "name": "unit.tests.",
                    "id": "A-111111",
                    "data": "1.2.3.4",
                    "ttl": 3600
                }, {
                    "name": "unit.tests.",
                    "id": "A-222222",
                    "data": "1.2.3.5",
                    "ttl": 3600
                }, {
                    "name": "unit.tests.",
                    "id": "A-333333",
                    "data": "1.2.3.6",
                    "ttl": 3600
                }]
            }
        return self._test_apply_with_data(TestData)

    def test_apply_multiple_updates_cross_zone(self):
        class TestData(object):
            OtherRecords = [
                {
                    "subdomain": 'foo',
                    "data": {
                        'type': 'A',
                        'ttl': 3600,
                        'value': '1.2.3.4'
                    }
                },
                {
                    "subdomain": 'bar',
                    "data": {
                        'type': 'A',
                        'ttl': 3600,
                        'value': '1.2.3.4'
                    }
                }
            ]
            OwnRecords = {
                "totalEntries": 2,
                "records": [{
                    "name": "foo.unit.tests.",
                    "id": "A-111111",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "bar.unit.tests.",
                    "id": "A-222222",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }]
            }
            ExpectChanges = True
            ExpectedAdditions = None
            ExpectedDeletions = None
            ExpectedUpdates = {
                "records": [{
                    "name": "bar.unit.tests.",
                    "id": "A-222222",
                    "data": "1.2.3.4",
                    "ttl": 3600
                }, {
                    "name": "foo.unit.tests.",
                    "id": "A-111111",
                    "data": "1.2.3.4",
                    "ttl": 3600
                }]
            }
        return self._test_apply_with_data(TestData)

    """
    def test_provider(self):
        expected = self._load_full_config()

        # No existing records -> creates for every record in expected
        with requests_mock() as mock:
            mock.get(re.compile('domains$'), status_code=200, text=LIST_DOMAINS_RESPONSE)
            mock.get(re.compile('records'), status_code=200, text=EMPTY_TEXT)

            plan = self.provider.plan(expected)
            self.assertTrue(mock.called)
            self.assertEquals(len(expected.records), len(plan.changes))

        # Used in a minute
        def assert_rrsets_callback(request, context):
            data = loads(request.body)
            self.assertEquals(expected_n, len(data['rrsets']))
            return ''

        with requests_mock() as mock:
            # post 201, is response to the create with data
            mock.patch(ANY, status_code=201, text=assert_rrsets_callback)

            self.assertEquals(expected_n, self.provider.apply(plan))

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
            # post 201, is response to the create with data
            mock.post(ANY, status_code=201, text=assert_rrsets_callback)

            plan = self.provider.plan(expected)
            self.assertEquals(expected_n, len(plan.changes))
            self.assertEquals(expected_n, self.provider.apply(plan))

        with requests_mock() as mock:
            # get 422's, unknown zone
            mock.get(ANY, status_code=422, text='')
            # patch 422's,
            data = {'error': "Key 'name' not present or not a String"}
            mock.patch(ANY, status_code=422, text=dumps(data))

            with self.assertRaises(HTTPError) as ctx:
                plan = self.provider.plan(expected)
                self.provider.apply(plan)
            response = ctx.exception.response
            self.assertEquals(422, response.status_code)
            self.assertTrue('error' in response.json())

        with requests_mock() as mock:
            # get 422's, unknown zone
            mock.get(ANY, status_code=422, text='')
            # patch 500's, things just blew up
            mock.patch(ANY, status_code=500, text='')

            with self.assertRaises(HTTPError):
                plan = self.provider.plan(expected)
                self.provider.apply(plan)

        with requests_mock() as mock:
            # get 422's, unknown zone
            mock.get(ANY, status_code=422, text='')
            # patch 500's, things just blew up
            mock.patch(ANY, status_code=422, text=dumps(not_found))
            # post 422's, something wrong with create
            mock.post(ANY, status_code=422, text='Hello Word!')

            with self.assertRaises(HTTPError):
                plan = self.provider.plan(expected)
                self.provider.apply(plan)
    """

    def test_plan_no_changes(self):
        expected = Zone('unit.tests.', [])
        expected.add_record(Record.new(expected, '', {
            'type': 'NS',
            'ttl': 600,
            'values': ['ns1.example.com.', 'ns2.example.com.']
        }))
        expected.add_record(Record.new(expected, '', {
            'type': 'A',
            'ttl': 600,
            'value': '1.2.3.4'
        }))

        with requests_mock() as mock:
            mock.get(re.compile('domains/.*/records'), status_code=200, text=RECORDS_EXISTING_NAMESERVERS)
            mock.get(re.compile('domains$'), status_code=200, text=LIST_DOMAINS_RESPONSE)

            plan = self.provider.plan(expected)

            self.assertTrue(mock.called)
            self.assertFalse(plan)

    def test_plan_remove_a_record(self):
        expected = Zone('unit.tests.', [])
        expected.add_record(Record.new(expected, '', {
            'type': 'NS',
            'ttl': 600,
            'values': ['ns1.example.com.', 'ns2.example.com.']
        }))

        with requests_mock() as mock:
            mock.get(re.compile('domains/.*/records'), status_code=200, text=RECORDS_EXISTING_NAMESERVERS)
            mock.get(re.compile('domains$'), status_code=200, text=LIST_DOMAINS_RESPONSE)

            plan = self.provider.plan(expected)
            self.assertTrue(mock.called)
            self.assertEquals(1, len(plan.changes))
            self.assertEqual(plan.changes[0].existing.ttl, 600)
            self.assertEqual(plan.changes[0].existing.values[0], '1.2.3.4')

    def test_plan_create_a_record(self):
        expected = Zone('unit.tests.', [])
        expected.add_record(Record.new(expected, '', {
            'type': 'NS',
            'ttl': 600,
            'values': ['ns1.example.com.', 'ns2.example.com.']
        }))
        expected.add_record(Record.new(expected, '', {
            'type': 'A',
            'ttl': 600,
            'values': ['1.2.3.4', '1.2.3.5']
        }))

        with requests_mock() as mock:
            mock.get(re.compile('domains/.*/records'), status_code=200, text=RECORDS_EXISTING_NAMESERVERS)
            mock.get(re.compile('domains$'), status_code=200, text=LIST_DOMAINS_RESPONSE)

            plan = self.provider.plan(expected)
            self.assertTrue(mock.called)
            self.assertEquals(1, len(plan.changes))
            self.assertEqual(plan.changes[0].new.ttl, 600)
            self.assertEqual(plan.changes[0].new.values[0], '1.2.3.4')
            self.assertEqual(plan.changes[0].new.values[1], '1.2.3.5')

    def test_plan_change_ttl(self):
        expected = Zone('unit.tests.', [])
        expected.add_record(Record.new(expected, '', {
            'type': 'NS',
            'ttl': 600,
            'values': ['ns1.example.com.', 'ns2.example.com.']
        }))
        expected.add_record(Record.new(expected, '', {
            'type': 'A',
            'ttl': 86400,
            'value': '1.2.3.4'
        }))

        with requests_mock() as mock:
            mock.get(re.compile('domains/.*/records'), status_code=200, text=RECORDS_EXISTING_NAMESERVERS)
            mock.get(re.compile('domains$'), status_code=200, text=LIST_DOMAINS_RESPONSE)

            plan = self.provider.plan(expected)

            self.assertTrue(mock.called)
            self.assertEqual(1, len(plan.changes))
            self.assertEqual(plan.changes[0].existing.ttl, 600)
            self.assertEqual(plan.changes[0].new.ttl, 86400)
            self.assertEqual(plan.changes[0].new.values[0], '1.2.3.4')
