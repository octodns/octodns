#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from json import loads, dumps
from os.path import dirname, join
from requests import HTTPError
from requests_mock import ANY, mock as requests_mock
from unittest import TestCase

from octodns.record import Record, TxtRecord
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


def _normalize_rrsets(rrsets):
    '''Normalizes PowerDNS RRsets for easier comparison.

        RRsets are in the form defined by the PowerDNS API
        (https://doc.powerdns.com/md/httpapi/api_spec/), i.e.  dicts with
        keys including `name', `type', `ttl', `records' and `comments'.

        :param rrsets: List of RRset dicts.
        :type  rrsets: list
    '''
    rrsets_clean = []
    for r in rrsets:
        if r['type'] in ('NS', 'SOA'):
            # NS records are overridden by nameserver_values and SOA
            # records are ignored by populate() so don't bother comparing
            # those.
            continue
        # Remove fields that aren't present in both the PATCH request _and_
        # GET response.
        r = r.copy()
        for field in ['comments', 'changetype']:
            if field in r:
                del r[field]
        # Record ordering shouldn't matter so sort consistently.
        if 'records' in r:
            r['records'] = sorted(r['records'],
                                  key=lambda r: r['content'])
        rrsets_clean.append(r)
    # rrset ordering shouldn't matter so sort consistently.
    return sorted(rrsets_clean, key=lambda r: (r['type'], r['name']))


class TestPowerDnsProvider(TestCase):

    def assertRrsetsEqual(self, first, second):
        """Checks whether two rrsets are equivalent when normalized."""
        first = _normalize_rrsets(first)
        second = _normalize_rrsets(second)
        self.assertEqual(first, second)

    def test_provider(self):
        provider = PowerDnsProvider('test', 'non.existant', 'api-key',
                                    nameserver_values=['8.8.8.8.',
                                                       '9.9.9.9.'])

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
        expected_n = len(expected.records) - 2
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
            # Verify that the records survive a round-trip.
            full_rrsets = loads(FULL_TEXT)['rrsets']
            self.assertRrsetsEqual(full_rrsets, data['rrsets'])
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
            mock.get(ANY, status_code=422, text='')
            # patch 422's, unknown zone
            mock.patch(ANY, status_code=422, text=dumps(not_found))
            # post 201, is response to the create with data
            mock.post(ANY, status_code=201, text=assert_rrsets_callback)

            plan = provider.plan(expected)
            self.assertEquals(expected_n, len(plan.changes))
            self.assertEquals(expected_n, provider.apply(plan))
            self.assertFalse(plan.exists)

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
        provider = PowerDnsProvider('test', 'non.existant', 'api-key')

        expected = Zone('unit.tests.', [])
        source = YamlProvider('test', join(dirname(__file__), 'config'))
        source.populate(expected)
        self.assertEquals(18, len(expected.records))

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

    def test_populate_escapes_semicolons(self):
        provider = PowerDnsProvider('test', 'non.existant', 'api-key')
        zone = Zone('unit.tests.', [])
        with requests_mock() as mock:
            mock.get(ANY, status_code=200, text=FULL_TEXT)
            provider.populate(zone)
        txts = [r for r in zone.records if isinstance(r, TxtRecord)]
        self.assertEquals(
            'v=DKIM1\\;k=rsa\\;s=email\\;h=sha256\\;'
            'p=A/kinda+of/long/string+with+numb3rs',
            txts[0].values[2])

    def test_apply_unescapes_semicolons(self):
        desired = Zone('unit.tests.', [])
        source = YamlProvider('test', join(dirname(__file__), 'config'))
        source.populate(desired)

        # save the rrsets sent to the API so we can assert them later.
        patch_rrsets = []

        def save_rrsets_callback(request, context):
            data = loads(request.body)
            patch_rrsets.extend(data['rrsets'])
            return ''

        provider = PowerDnsProvider('test', 'non.existant', 'api-key')
        with requests_mock() as mock:
            mock.get(ANY, status_code=200, text=EMPTY_TEXT)
            # post 201, is response to the create with data
            mock.patch(ANY, status_code=201, text=save_rrsets_callback)
            plan = provider.plan(desired)
            provider.apply(plan)

        txts = [c for c in patch_rrsets if c['type'] == 'TXT']
        self.assertEquals(
            '"v=DKIM1;k=rsa;s=email;h=sha256;'
            'p=A/kinda+of/long/string+with+numb3rs"',
            txts[0]['records'][2]['content'])

    def test_existing_nameservers(self):
        ns_values = ['8.8.8.8.', '9.9.9.9.']
        provider = PowerDnsProvider('test', 'non.existant', 'api-key',
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
