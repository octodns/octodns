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
from octodns.provider.constellix import \
    ConstellixProvider, ConstellixClientBadRequest
from octodns.provider.yaml import YamlProvider
from octodns.zone import Zone


class TestConstellixProvider(TestCase):
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

    # Add a dynamic record
    expected.add_record(Record.new(expected, 'www.dynamic', {
        'ttl': 300,
        'type': 'A',
        'value': [
            '1.2.3.4',
            '1.2.3.5'
        ],
        'dynamic': {
            'pools': {
                'two': {
                    'values': [{
                        'value': '1.2.3.4',
                        'weight': 1
                    }, {
                        'value': '1.2.3.5',
                        'weight': 1
                    }],
                },
            },
            'rules': [{
                'pool': 'two',
            }],
        },
    }))

    for record in list(expected.records):
        if record.name == 'sub' and record._type == 'NS':
            expected._remove_record(record)
            break

    def test_populate(self):
        provider = ConstellixProvider('test', 'api', 'secret')

        # Bad auth
        with requests_mock() as mock:
            mock.get(ANY, status_code=401,
                     text='{"errors": ["Unable to authenticate token"]}')

            with self.assertRaises(Exception) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals('Unauthorized', text_type(ctx.exception))

        # Bad request
        with requests_mock() as mock:
            mock.get(ANY, status_code=400,
                     text='{"errors": ["\\"unittests\\" is not '
                          'a valid domain name"]}')

            with self.assertRaises(Exception) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals('\n  - "unittests" is not a valid domain name',
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
            base = 'https://api.dns.constellix.com/v1'
            with open('tests/fixtures/constellix-domains.json') as fh:
                mock.get('{}{}'.format(base, '/domains'), text=fh.read())
            with open('tests/fixtures/constellix-records.json') as fh:
                mock.get('{}{}'.format(base, '/domains/123123/records'),
                         text=fh.read())
            with open('tests/fixtures/constellix-pools.json') as fh:
                mock.get('{}{}'.format(base, '/pools/A'),
                         text=fh.read())

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

    def test_apply(self):
        provider = ConstellixProvider('test', 'api', 'secret')

        resp = Mock()
        resp.json = Mock()
        provider._client._request = Mock(return_value=resp)

        # non-existent domain, create everything
        resp.json.side_effect = [
            [],  # no domains returned during populate
            [{
                'id': 123123,
                'name': 'unit.tests'
            }],  # domain created in apply
            [],  # No pools returned during populate
            [{
                "id": 1808520,
                "name": "unit.tests.:www.dynamic:A:two",
            }]   # pool created in apply
        ]

        plan = provider.plan(self.expected)

        # No root NS, no ignored, no excluded, no unsupported
        n = len(self.expected.records) - 5
        self.assertEquals(n, len(plan.changes))
        self.assertEquals(n, provider.apply(plan))

        provider._client._request.assert_has_calls([
            # get all domains to build the cache
            call('GET', '/domains'),
            # created the domain
            call('POST', '/domains', data={'names': ['unit.tests']})
        ])

        # Check we tried to get our pool
        provider._client._request.assert_has_calls([
            # get all pools to build the cache
            call('GET', '/pools/A'),
            # created the pool
            call('POST', '/pools/A', data={
                'name': 'unit.tests.:www.dynamic:A:two',
                'type': 'A',
                'numReturn': 1,
                'minAvailableFailover': 1,
                'ttl': 300,
                'values': [{
                    "value": "1.2.3.4",
                    "weight": 1
                }, {
                    "value": "1.2.3.5",
                    "weight": 1
                }]
            })
        ])

        # These two checks are broken up so that ordering doesn't break things.
        # Python3 doesn't make the calls in a consistent order so different
        # things follow the GET / on different runs
        provider._client._request.assert_has_calls([
            call('POST', '/domains/123123/records/SRV', data={
                'roundRobin': [{
                    'priority': 10,
                    'weight': 20,
                    'value': 'foo-1.unit.tests.',
                    'port': 30
                }, {
                    'priority': 12,
                    'weight': 20,
                    'value': 'foo-2.unit.tests.',
                    'port': 30
                }],
                'name': '_srv._tcp',
                'ttl': 600,
            }),
        ])

        self.assertEquals(21, provider._client._request.call_count)

        provider._client._request.reset_mock()

        provider._client.records = Mock(return_value=[
            {
                'id': 11189897,
                'type': 'A',
                'name': 'www',
                'ttl': 300,
                'recordOption': 'roundRobin',
                'value': [
                    '1.2.3.4',
                    '2.2.3.4',
                ]
            }, {
                'id': 11189898,
                'type': 'A',
                'name': 'ttl',
                'ttl': 600,
                'recordOption': 'roundRobin',
                'value': [
                    '3.2.3.4'
                ]
            },  {
                'id': 11189899,
                'type': 'ALIAS',
                'name': 'alias',
                'ttl': 600,
                'recordOption': 'roundRobin',
                'value': [{
                    'value': 'aname.unit.tests.'
                }]
            }, {
                "id": 1808520,
                "type": "A",
                "name": "www.dynamic",
                "recordOption": "pools",
                "ttl": 300,
                "value": [],
                "pools": [
                    1808521
                ]
            }
        ])

        provider._client.pools = Mock(return_value=[{
            "id": 1808521,
            "name": "unit.tests.:www.dynamic:A:two",
            "type": "A",
            "values": [
                {
                    "value": "1.2.3.4",
                    "weight": 1
                },
                {
                    "value": "1.2.3.5",
                    "weight": 1
                }
            ]
        }])

        # Domain exists, we don't care about return
        resp.json.side_effect = [
            ['{}'],
            ['{}'],
        ]

        wanted = Zone('unit.tests.', [])
        wanted.add_record(Record.new(wanted, 'ttl', {
            'ttl': 300,
            'type': 'A',
            'value': '3.2.3.4'
        }))

        wanted.add_record(Record.new(wanted, 'www.dynamic', {
            'ttl': 300,
            'type': 'A',
            'value': [
                '1.2.3.4'
            ],
            'dynamic': {
                'pools': {
                    'two': {
                        'values': [{
                            'value': '1.2.3.4',
                            'weight': 1
                        }],
                    },
                },
                'rules': [{
                    'pool': 'two',
                }],
            },
        }))

        plan = provider.plan(wanted)
        self.assertEquals(4, len(plan.changes))
        self.assertEquals(4, provider.apply(plan))

        # recreate for update, and deletes for the 2 parts of the other
        provider._client._request.assert_has_calls([
            call('POST', '/domains/123123/records/A', data={
                'roundRobin': [{
                    'value': '3.2.3.4'
                }],
                'name': 'ttl',
                'ttl': 300
            }),
            call('PUT', '/pools/A/1808521', data={
                'name': 'unit.tests.:www.dynamic:A:two',
                'type': 'A',
                'numReturn': 1,
                'minAvailableFailover': 1,
                'ttl': 300,
                'id': 1808521,
                'values': [{
                    "value": "1.2.3.4",
                    "weight": 1
                }]
            }),
            call('DELETE', '/domains/123123/records/A/11189897'),
            call('DELETE', '/domains/123123/records/A/11189898'),
            call('DELETE', '/domains/123123/records/ANAME/11189899'),
        ], any_order=True)

    def test_dynamic_record_failures(self):
        provider = ConstellixProvider('test', 'api', 'secret')

        resp = Mock()
        resp.json = Mock()
        provider._client._request = Mock(return_value=resp)

        # Let's handle some failures for pools - first if it's not a simple
        # weighted pool - we'll be OK as we assume a weight of 1 for all
        # entries
        provider._client._request.reset_mock()
        provider._client.records = Mock(return_value=[
            {
                "id": 1808520,
                "type": "A",
                "name": "www.dynamic",
                "recordOption": "pools",
                "ttl": 300,
                "value": [],
                "pools": [
                    1808521
                ]
            }
        ])

        provider._client.pools = Mock(return_value=[{
            "id": 1808521,
            "name": "unit.tests.:www.dynamic:A:two",
            "type": "A",
            "values": [
                {
                    "value": "1.2.3.4",
                    "weight": 1
                }
            ]
        }])

        wanted = Zone('unit.tests.', [])

        resp.json.side_effect = [
            ['{}'],
            ['{}'],
        ]
        wanted.add_record(Record.new(wanted, 'www.dynamic', {
            'ttl': 300,
            'type': 'A',
            'value': [
                '1.2.3.4'
            ],
            'dynamic': {
                'pools': {
                    'two': {
                        'values': [{
                            'value': '1.2.3.4'
                        }],
                    },
                },
                'rules': [{
                    'pool': 'two',
                }],
            },
        }))

        plan = provider.plan(wanted)
        self.assertIsNone(plan)

    def test_dynamic_record_updates(self):
        provider = ConstellixProvider('test', 'api', 'secret')

        # Constellix API can return an error if you try and update a pool and
        # don't change anything, so let's test we handle it silently

        provider._client.records = Mock(return_value=[
            {
                "id": 1808520,
                "type": "A",
                "name": "www.dynamic",
                "recordOption": "pools",
                "ttl": 300,
                "value": [],
                "pools": [
                    1808521
                ]
            }
        ])

        provider._client.pools = Mock(return_value=[{
            "id": 1808521,
            "name": "unit.tests.:www.dynamic:A:two",
            "type": "A",
            "values": [
                {
                    "value": "1.2.3.4",
                    "weight": 1
                }
            ]
        }])

        wanted = Zone('unit.tests.', [])

        wanted.add_record(Record.new(wanted, 'www.dynamic', {
            'ttl': 300,
            'type': 'A',
            'value': [
                '1.2.3.4'
            ],
            'dynamic': {
                'pools': {
                    'two': {
                        'values': [{
                            'value': '1.2.3.5'
                        }],
                    },
                },
                'rules': [{
                    'pool': 'two',
                }],
            },
        }))

        # Try an error we can handle
        with requests_mock() as mock:
            mock.get(ANY, status_code=200,
                     text='{}')
            mock.delete(ANY, status_code=200,
                        text='{}')
            mock.put("https://api.dns.constellix.com/v1/pools/A/1808521",
                     status_code=400,
                     text='{"errors": [\"no changes to save\"]}')
            mock.post(ANY, status_code=200,
                      text='[{"id": 1234}]')

            plan = provider.plan(wanted)
            self.assertEquals(1, len(plan.changes))
            self.assertEquals(1, provider.apply(plan))

        # Now what happens if an error happens that we can't handle
        with requests_mock() as mock:
            mock.get(ANY, status_code=200,
                     text='{}')
            mock.delete(ANY, status_code=200,
                        text='{}')
            mock.put("https://api.dns.constellix.com/v1/pools/A/1808521",
                     status_code=400,
                     text='{"errors": [\"generic error\"]}')
            mock.post(ANY, status_code=200,
                      text='[{"id": 1234}]')

            plan = provider.plan(wanted)
            self.assertEquals(1, len(plan.changes))
            with self.assertRaises(ConstellixClientBadRequest):
                provider.apply(plan)

    def test_pools_that_are_notfound(self):
        provider = ConstellixProvider('test', 'api', 'secret')

        provider._client.pools = Mock(return_value=[{
            "id": 1808521,
            "name": "unit.tests.:www.dynamic:A:two",
            "type": "A",
            "values": [
                {
                    "value": "1.2.3.4",
                    "weight": 1
                }
            ]
        }])

        self.assertIsNone(provider._client.pool_by_id('A', 1))
        self.assertIsNone(provider._client.pool('A', 'foobar'))
