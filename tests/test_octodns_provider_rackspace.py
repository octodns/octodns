#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import json
import re
from unittest import TestCase
from urlparse import urlparse

from requests import HTTPError
from requests_mock import ANY, mock as requests_mock

from octodns.provider.rackspace import RackspaceProvider
from octodns.record import Record
from octodns.zone import Zone

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


class TestRackspaceProvider(TestCase):
    def setUp(self):
        self.maxDiff = 1000
        with requests_mock() as mock:
            mock.post(ANY, status_code=200, text=AUTH_RESPONSE)
            self.provider = RackspaceProvider('identity', 'test', 'api-key',
                                              '0')
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
            exists = self.provider.populate(zone)
            self.assertEquals(set(), zone.records)
            self.assertTrue(mock.called_once)
            self.assertFalse(exists)

    def test_multipage_populate(self):
        with requests_mock() as mock:
            mock.get(re.compile('domains$'), status_code=200,
                     text=LIST_DOMAINS_RESPONSE)
            mock.get(re.compile('records'), status_code=200,
                     text=RECORDS_PAGE_1)
            mock.get(re.compile('records.*offset=3'), status_code=200,
                     text=RECORDS_PAGE_2)

            zone = Zone('unit.tests.', [])
            self.provider.populate(zone)
            self.assertEquals(5, len(zone.records))

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
            mock.get(re.compile('domains$'), status_code=200,
                     text=LIST_DOMAINS_RESPONSE)
            mock.get(re.compile('records'), status_code=200, text=EMPTY_TEXT)

            plan = self.provider.plan(expected)
            self.assertTrue(mock.called)
            self.assertTrue(plan.exists)

            # OctoDNS does not propagate top-level NS records.
            self.assertEquals(1, len(plan.changes))

    def test_fqdn_a_record(self):
        expected = Zone('example.com.', [])
        # expected.add_record(Record.new(expected, 'foo', '1.2.3.4'))

        with requests_mock() as list_mock:
            list_mock.get(re.compile('domains$'), status_code=200,
                          text=LIST_DOMAINS_RESPONSE)
            list_mock.get(re.compile('records'), status_code=200,
                          json={'records': [
                              {'type': 'A',
                               'name': 'foo.example.com',
                               'id': 'A-111111',
                               'data': '1.2.3.4',
                               'ttl': 300}]})
            plan = self.provider.plan(expected)
            self.assertTrue(list_mock.called)
            self.assertEqual(1, len(plan.changes))
            self.assertTrue(
                plan.changes[0].existing.fqdn == 'foo.example.com.')

        with requests_mock() as mock:
            def _assert_deleting(request, context):
                parts = urlparse(request.url)
                self.assertEqual('id=A-111111', parts.query)

            mock.get(re.compile('domains$'), status_code=200,
                     text=LIST_DOMAINS_RESPONSE)
            mock.delete(re.compile('domains/.*/records?.*'), status_code=202,
                        text=_assert_deleting)
            self.provider.apply(plan)
            self.assertTrue(mock.called)

    def _test_apply_with_data(self, data):
        expected = Zone('unit.tests.', [])
        for record in data.OtherRecords:
            expected.add_record(
                Record.new(expected, record['subdomain'], record['data']))

        with requests_mock() as list_mock:
            list_mock.get(re.compile('domains$'), status_code=200,
                          text=LIST_DOMAINS_RESPONSE)
            list_mock.get(re.compile('records'), status_code=200,
                          json=data.OwnRecords)
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
                        self.assertEqual(request.headers['content-type'],
                                         'application/json')
                        self.assertDictEqual(expected,
                                             json.loads(request.body))
                    else:
                        parts = urlparse(request.url)
                        self.assertEqual(expected, parts.query)
                    return ''

                return _assert_sending_right_body

            mock.get(re.compile('domains$'), status_code=200,
                     text=LIST_DOMAINS_RESPONSE)
            mock.post(re.compile('domains/.*/records$'), status_code=202,
                      text=make_assert_sending_right_body(
                          data.ExpectedAdditions))
            mock.delete(re.compile('domains/.*/records?.*'), status_code=202,
                        text=make_assert_sending_right_body(
                            data.ExpectedDeletions))
            mock.put(re.compile('domains/.*/records$'), status_code=202,
                     text=make_assert_sending_right_body(data.ExpectedUpdates))

            self.provider.apply(plan)
            self.assertTrue(data.ExpectedAdditions is None or "POST" in called)
            self.assertTrue(
                data.ExpectedDeletions is None or "DELETE" in called)
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
                    "name": "unit.tests",
                    "id": "A-111111",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "unit.tests",
                    "id": "A-222222",
                    "type": "A",
                    "data": "1.2.3.5",
                    "ttl": 300
                }, {
                    "name": "unit.tests",
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
                    "name": "foo.unit.tests",
                    "id": "A-111111",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "bar.unit.tests",
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
                    "name": "unit.tests",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests",
                    "type": "NS",
                    "data": "ns.example.com",
                    "ttl": 300
                }]
            }
            ExpectedDeletions = None
            ExpectedUpdates = None

        return self._test_apply_with_data(TestData)

    def test_apply_create_MX(self):
        class TestData(object):
            OtherRecords = [
                {
                    "subdomain": '',
                    "data": {
                        'type': 'MX',
                        'ttl': 300,
                        'value': {
                            'value': 'mail1.example.com.',
                            'priority': 1,
                        }
                    }
                },
                {
                    "subdomain": 'foo',
                    "data": {
                        'type': 'MX',
                        'ttl': 300,
                        'value': {
                            'value': 'mail2.example.com.',
                            'priority': 2
                        }
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
                    "name": "foo.unit.tests",
                    "type": "MX",
                    "data": "mail2.example.com",
                    "priority": 2,
                    "ttl": 300
                }, {
                    "name": "unit.tests",
                    "type": "MX",
                    "data": "mail1.example.com",
                    "priority": 1,
                    "ttl": 300
                }]
            }
            ExpectedDeletions = None
            ExpectedUpdates = None

        return self._test_apply_with_data(TestData)

    def test_apply_multiple_additions_splatting(self):
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
                    "name": "unit.tests",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "unit.tests",
                    "type": "A",
                    "data": "1.2.3.5",
                    "ttl": 300
                }, {
                    "name": "unit.tests",
                    "type": "A",
                    "data": "1.2.3.6",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests",
                    "type": "NS",
                    "data": "ns1.example.com",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests",
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
            }, {
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
                    "name": "bar.unit.tests",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests",
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
                    "name": "unit.tests",
                    "id": "A-111111",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests",
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
                    "name": "unit.tests",
                    "id": "A-111111",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "unit.tests",
                    "id": "A-222222",
                    "type": "A",
                    "data": "1.2.3.5",
                    "ttl": 300
                }, {
                    "name": "unit.tests",
                    "id": "A-333333",
                    "type": "A",
                    "data": "1.2.3.6",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests",
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
                    "name": "unit.tests",
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
                    "name": "unit.tests",
                    "id": "A-111111",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "foo.unit.tests",
                    "id": "A-222222",
                    "type": "A",
                    "data": "1.2.3.5",
                    "ttl": 300
                }, {
                    "name": "bar.unit.tests",
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

    def test_apply_delete_cname(self):
        class TestData(object):
            OtherRecords = []
            OwnRecords = {
                "totalEntries": 3,
                "records": [{
                    "name": "foo.unit.tests",
                    "id": "CNAME-111111",
                    "type": "CNAME",
                    "data": "a.example.com",
                    "ttl": 300
                }]
            }
            ExpectChanges = True
            ExpectedAdditions = None
            ExpectedDeletions = "id=CNAME-111111"
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
                    "name": "unit.tests",
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
                    "name": "unit.tests",
                    "id": "A-111111",
                    "data": "1.2.3.4",
                    "ttl": 3600
                }]
            }

        return self._test_apply_with_data(TestData)

    def test_apply_update_TXT(self):
        class TestData(object):
            OtherRecords = [
                {
                    "subdomain": '',
                    "data": {
                        'type': 'TXT',
                        'ttl': 300,
                        'value': 'othervalue'
                    }
                }
            ]
            OwnRecords = {
                "totalEntries": 1,
                "records": [{
                    "name": "unit.tests",
                    "id": "TXT-111111",
                    "type": "TXT",
                    "data": "somevalue",
                    "ttl": 300
                }]
            }
            ExpectChanges = True
            ExpectedAdditions = {
                "records": [{
                    "name": "unit.tests",
                    "type": "TXT",
                    "data": "othervalue",
                    "ttl": 300
                }]
            }
            ExpectedDeletions = 'id=TXT-111111'
            ExpectedUpdates = None

        return self._test_apply_with_data(TestData)

    def test_apply_update_MX(self):
        class TestData(object):
            OtherRecords = [
                {
                    "subdomain": '',
                    "data": {
                        'type': 'MX',
                        'ttl': 300,
                        'value': {u'priority': 50, u'value': 'mx.test.com.'}
                    }
                }
            ]
            OwnRecords = {
                "totalEntries": 1,
                "records": [{
                    "name": "unit.tests",
                    "id": "MX-111111",
                    "type": "MX",
                    "priority": 20,
                    "data": "mx.test.com",
                    "ttl": 300
                }]
            }
            ExpectChanges = True
            ExpectedAdditions = {
                "records": [{
                    "name": "unit.tests",
                    "type": "MX",
                    "priority": 50,
                    "data": "mx.test.com",
                    "ttl": 300
                }]
            }
            ExpectedDeletions = 'id=MX-111111'
            ExpectedUpdates = None

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
                    "name": "unit.tests",
                    "id": "A-111111",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "unit.tests",
                    "id": "A-222222",
                    "type": "A",
                    "data": "1.2.3.5",
                    "ttl": 300
                }, {
                    "name": "unit.tests",
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
                    "name": "unit.tests",
                    "id": "A-222222",
                    "data": "1.2.3.5",
                    "ttl": 3600
                }, {
                    "name": "unit.tests",
                    "id": "A-111111",
                    "data": "1.2.3.4",
                    "ttl": 3600
                }, {
                    "name": "unit.tests",
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
                    "name": "foo.unit.tests",
                    "id": "A-111111",
                    "type": "A",
                    "data": "1.2.3.4",
                    "ttl": 300
                }, {
                    "name": "bar.unit.tests",
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
                    "name": "bar.unit.tests",
                    "id": "A-222222",
                    "data": "1.2.3.4",
                    "ttl": 3600
                }, {
                    "name": "foo.unit.tests",
                    "id": "A-111111",
                    "data": "1.2.3.4",
                    "ttl": 3600
                }]
            }

        return self._test_apply_with_data(TestData)
