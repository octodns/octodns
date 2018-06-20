#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from dyn.tm.errors import DynectGetError
from dyn.tm.services.dsf import DSFResponsePool
from json import loads
from mock import MagicMock, call, patch
from unittest import TestCase

from octodns.record import Create, Delete, Record, Update
from octodns.provider.base import Plan
from octodns.provider.dyn import DynProvider, _CachingDynZone, DSFMonitor
from octodns.zone import Zone

from helpers import SimpleProvider


class _DummyPool(object):

    def __init__(self, response_pool_id):
        self.response_pool_id = response_pool_id
        self.deleted = False

    def delete(self):
        self.deleted = True


class TestDynProvider(TestCase):
    expected = Zone('unit.tests.', [])
    for name, data in (
        ('', {
            'type': 'A',
            'ttl': 300,
            'values': ['1.2.3.4']
        }),
        ('cname', {
            'type': 'CNAME',
            'ttl': 301,
            'value': 'unit.tests.'
        }),
        ('', {
            'type': 'MX',
            'ttl': 302,
            'values': [{
                'preference': 10,
                'exchange': 'smtp-1.unit.tests.'
            }, {
                'preference': 20,
                'exchange': 'smtp-2.unit.tests.'
            }]
        }),
        ('naptr', {
            'type': 'NAPTR',
            'ttl': 303,
            'values': [{
                'order': 100,
                'preference': 101,
                'flags': 'U',
                'service': 'SIP+D2U',
                'regexp': '!^.*$!sip:info@foo.example.com!',
                'replacement': '.',
            }, {
                'order': 200,
                'preference': 201,
                'flags': 'U',
                'service': 'SIP+D2U',
                'regexp': '!^.*$!sip:info@bar.example.com!',
                'replacement': '.',
            }]
        }),
        ('sub', {
            'type': 'NS',
            'ttl': 3600,
            'values': ['ns3.p10.dynect.net.', 'ns3.p10.dynect.net.'],
        }),
        ('ptr', {
            'type': 'PTR',
            'ttl': 304,
            'value': 'xx.unit.tests.'
        }),
        ('spf', {
            'type': 'SPF',
            'ttl': 305,
            'values': ['v=spf1 ip4:192.168.0.1/16-all', 'v=spf1 -all'],
        }),
        ('', {
            'type': 'SSHFP',
            'ttl': 306,
            'value': {
                'algorithm': 1,
                'fingerprint_type': 1,
                'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
            }
        }),
        ('_srv._tcp', {
            'type': 'SRV',
            'ttl': 307,
            'values': [{
                'priority': 11,
                'weight': 12,
                'port': 10,
                'target': 'foo-1.unit.tests.'
            }, {
                'priority': 21,
                'weight': 22,
                'port': 20,
                'target': 'foo-2.unit.tests.'
            }]}),
        ('', {
            'type': 'CAA',
            'ttl': 308,
            'values': [{
                'flags': 0,
                'tag': 'issue',
                'value': 'ca.unit.tests'
            }]})):
        expected.add_record(Record.new(expected, name, data))

    @classmethod
    def setUpClass(self):
        # Get the DynectSession creation out of the way so that tests can
        # ignore it
        with patch('dyn.core.SessionEngine.execute',
                   return_value={'status': 'success'}):
            provider = DynProvider('test', 'cust', 'user', 'pass')
            provider._check_dyn_sess()

    def setUp(self):
        # Flush our zone to ensure we start fresh
        _CachingDynZone.flush_zone(self.expected.name[:-1])

    @patch('dyn.core.SessionEngine.execute')
    def test_populate_non_existent(self, execute_mock):
        provider = DynProvider('test', 'cust', 'user', 'pass')

        # Test Zone create
        execute_mock.side_effect = [
            DynectGetError('foo'),
        ]
        got = Zone('unit.tests.', [])
        provider.populate(got)
        execute_mock.assert_has_calls([
            call('/Zone/unit.tests/', 'GET', {}),
        ])
        self.assertEquals(set(), got.records)

    @patch('dyn.core.SessionEngine.execute')
    def test_populate(self, execute_mock):
        provider = DynProvider('test', 'cust', 'user', 'pass')

        # Test Zone create
        execute_mock.side_effect = [
            # get Zone
            {'data': {}},
            # get_all_records
            {'data': {
                'a_records': [{
                    'fqdn': 'unit.tests',
                    'rdata': {'address': '1.2.3.4'},
                    'record_id': 1,
                    'record_type': 'A',
                    'ttl': 300,
                    'zone': 'unit.tests',
                }],
                'cname_records': [{
                    'fqdn': 'cname.unit.tests',
                    'rdata': {'cname': 'unit.tests.'},
                    'record_id': 2,
                    'record_type': 'CNAME',
                    'ttl': 301,
                    'zone': 'unit.tests',
                }],
                'ns_records': [{
                    'fqdn': 'unit.tests',
                    'rdata': {'nsdname': 'ns1.p10.dynect.net.'},
                    'record_id': 254597562,
                    'record_type': 'NS',
                    'service_class': '',
                    'ttl': 3600,
                    'zone': 'unit.tests'
                }, {
                    'fqdn': 'unit.tests',
                    'rdata': {'nsdname': 'ns2.p10.dynect.net.'},
                    'record_id': 254597563,
                    'record_type': 'NS',
                    'service_class': '',
                    'ttl': 3600,
                    'zone': 'unit.tests'
                }, {
                    'fqdn': 'unit.tests',
                    'rdata': {'nsdname': 'ns3.p10.dynect.net.'},
                    'record_id': 254597564,
                    'record_type': 'NS',
                    'service_class': '',
                    'ttl': 3600,
                    'zone': 'unit.tests'
                }, {
                    'fqdn': 'unit.tests',
                    'rdata': {'nsdname': 'ns4.p10.dynect.net.'},
                    'record_id': 254597565,
                    'record_type': 'NS',
                    'service_class': '',
                    'ttl': 3600,
                    'zone': 'unit.tests'
                }, {
                    'fqdn': 'sub.unit.tests',
                    'rdata': {'nsdname': 'ns3.p10.dynect.net.'},
                    'record_id': 254597564,
                    'record_type': 'NS',
                    'service_class': '',
                    'ttl': 3600,
                    'zone': 'unit.tests'
                }, {
                    'fqdn': 'sub.unit.tests',
                    'rdata': {'nsdname': 'ns3.p10.dynect.net.'},
                    'record_id': 254597564,
                    'record_type': 'NS',
                    'service_class': '',
                    'ttl': 3600,
                    'zone': 'unit.tests'
                }],
                'mx_records': [{
                    'fqdn': 'unit.tests',
                    'rdata': {'exchange': 'smtp-1.unit.tests.',
                              'preference': 10},
                    'record_id': 3,
                    'record_type': 'MX',
                    'ttl': 302,
                    'zone': 'unit.tests',
                }, {
                    'fqdn': 'unit.tests',
                    'rdata': {'exchange': 'smtp-2.unit.tests.',
                              'preference': 20},
                    'record_id': 4,
                    'record_type': 'MX',
                    'ttl': 302,
                    'zone': 'unit.tests',
                }],
                'naptr_records': [{
                    'fqdn': 'naptr.unit.tests',
                    'rdata': {'flags': 'U',
                              'order': 100,
                              'preference': 101,
                              'regexp': '!^.*$!sip:info@foo.example.com!',
                              'replacement': '.',
                              'services': 'SIP+D2U'},
                    'record_id': 5,
                    'record_type': 'MX',
                    'ttl': 303,
                    'zone': 'unit.tests',
                }, {
                    'fqdn': 'naptr.unit.tests',
                    'rdata': {'flags': 'U',
                              'order': 200,
                              'preference': 201,
                              'regexp': '!^.*$!sip:info@bar.example.com!',
                              'replacement': '.',
                              'services': 'SIP+D2U'},
                    'record_id': 6,
                    'record_type': 'MX',
                    'ttl': 303,
                    'zone': 'unit.tests',
                }],
                'ptr_records': [{
                    'fqdn': 'ptr.unit.tests',
                    'rdata': {'ptrdname': 'xx.unit.tests.'},
                    'record_id': 7,
                    'record_type': 'PTR',
                    'ttl': 304,
                    'zone': 'unit.tests',
                }],
                'soa_records': [{
                    'fqdn': 'unit.tests',
                    'rdata': {'txtdata': 'ns1.p16.dynect.net. '
                              'hostmaster.unit.tests. 4 3600 600 604800 1800'},
                    'record_id': 99,
                    'record_type': 'SOA',
                    'ttl': 299,
                    'zone': 'unit.tests',
                }],
                'spf_records': [{
                    'fqdn': 'spf.unit.tests',
                    'rdata': {'txtdata': 'v=spf1 ip4:192.168.0.1/16-all'},
                    'record_id': 8,
                    'record_type': 'SPF',
                    'ttl': 305,
                    'zone': 'unit.tests',
                }, {
                    'fqdn': 'spf.unit.tests',
                    'rdata': {'txtdata': 'v=spf1 -all'},
                    'record_id': 8,
                    'record_type': 'SPF',
                    'ttl': 305,
                    'zone': 'unit.tests',
                }],
                'sshfp_records': [{
                    'fqdn': 'unit.tests',
                    'rdata': {'algorithm': 1,
                              'fingerprint':
                              'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                              'fptype': 1},
                    'record_id': 9,
                    'record_type': 'SSHFP',
                    'ttl': 306,
                    'zone': 'unit.tests',
                }],
                'srv_records': [{
                    'fqdn': '_srv._tcp.unit.tests',
                    'rdata': {'port': 10,
                              'priority': 11,
                              'target': 'foo-1.unit.tests.',
                              'weight': 12},
                    'record_id': 10,
                    'record_type': 'SRV',
                    'ttl': 307,
                    'zone': 'unit.tests',
                }, {
                    'fqdn': '_srv._tcp.unit.tests',
                    'rdata': {'port': 20,
                              'priority': 21,
                              'target': 'foo-2.unit.tests.',
                              'weight': 22},
                    'record_id': 11,
                    'record_type': 'SRV',
                    'ttl': 307,
                    'zone': 'unit.tests',
                }],
                'caa_records': [{
                    'fqdn': 'unit.tests',
                    'rdata': {'flags': 0,
                              'tag': 'issue',
                              'value': 'ca.unit.tests'},
                    'record_id': 12,
                    'record_type': 'cAA',
                    'ttl': 308,
                    'zone': 'unit.tests',
                }],
            }}
        ]
        got = Zone('unit.tests.', [])
        provider.populate(got)
        execute_mock.assert_has_calls([
            call('/Zone/unit.tests/', 'GET', {}),
            call('/AllRecord/unit.tests/unit.tests./', 'GET', {'detail': 'Y'})
        ])
        changes = self.expected.changes(got, SimpleProvider())
        self.assertEquals([], changes)

    @patch('dyn.core.SessionEngine.execute')
    def test_sync(self, execute_mock):
        provider = DynProvider('test', 'cust', 'user', 'pass')

        # Test Zone create
        execute_mock.side_effect = [
            # No such zone, during populate
            DynectGetError('foo'),
            # No such zone, during sync
            DynectGetError('foo'),
            # get empty Zone
            {'data': {}},
            # get zone we can modify & delete with
            {'data': {
                # A top-level to delete
                'a_records': [{
                    'fqdn': 'unit.tests',
                    'rdata': {'address': '1.2.3.4'},
                    'record_id': 1,
                    'record_type': 'A',
                    'ttl': 30,
                    'zone': 'unit.tests',
                }, {
                    'fqdn': 'a.unit.tests',
                    'rdata': {'address': '2.3.4.5'},
                    'record_id': 2,
                    'record_type': 'A',
                    'ttl': 30,
                    'zone': 'unit.tests',
                }],
                # A node to delete
                'cname_records': [{
                    'fqdn': 'cname.unit.tests',
                    'rdata': {'cname': 'unit.tests.'},
                    'record_id': 3,
                    'record_type': 'CNAME',
                    'ttl': 30,
                    'zone': 'unit.tests',
                }],
                # A record to leave alone
                'ptr_records': [{
                    'fqdn': 'ptr.unit.tests',
                    'rdata': {'ptrdname': 'xx.unit.tests.'},
                    'record_id': 4,
                    'record_type': 'PTR',
                    'ttl': 30,
                    'zone': 'unit.tests',
                }],
                # A record to modify
                'srv_records': [{
                    'fqdn': '_srv._tcp.unit.tests',
                    'rdata': {'port': 10,
                              'priority': 11,
                              'target': 'foo-1.unit.tests.',
                              'weight': 12},
                    'record_id': 5,
                    'record_type': 'SRV',
                    'ttl': 30,
                    'zone': 'unit.tests',
                }, {
                    'fqdn': '_srv._tcp.unit.tests',
                    'rdata': {'port': 20,
                              'priority': 21,
                              'target': 'foo-2.unit.tests.',
                              'weight': 22},
                    'record_id': 6,
                    'record_type': 'SRV',
                    'ttl': 30,
                    'zone': 'unit.tests',
                }],
            }}
        ]

        # No existing records, create all
        with patch('dyn.tm.zones.Zone.add_record') as add_mock:
            with patch('dyn.tm.zones.Zone._update') as update_mock:
                plan = provider.plan(self.expected)
                update_mock.assert_not_called()
                provider.apply(plan)
                update_mock.assert_called()
                self.assertFalse(plan.exists)
            add_mock.assert_called()
            # Once for each dyn record (8 Records, 2 of which have dual values)
            self.assertEquals(15, len(add_mock.call_args_list))
        execute_mock.assert_has_calls([call('/Zone/unit.tests/', 'GET', {}),
                                       call('/Zone/unit.tests/', 'GET', {})])
        self.assertEquals(10, len(plan.changes))

        execute_mock.reset_mock()

        # Delete one and modify another
        new = Zone('unit.tests.', [])
        for name, data in (
            ('a', {
                'type': 'A',
                'ttl': 30,
                'value': '2.3.4.5'
            }),
            ('ptr', {
                'type': 'PTR',
                'ttl': 30,
                'value': 'xx.unit.tests.'
            }),
            ('_srv._tcp', {
                'type': 'SRV',
                'ttl': 30,
                'values': [{
                    'priority': 31,
                    'weight': 12,
                    'port': 10,
                    'target': 'foo-1.unit.tests.'
                }, {
                    'priority': 21,
                    'weight': 22,
                    'port': 20,
                    'target': 'foo-2.unit.tests.'
                }]})):
            new.add_record(Record.new(new, name, data))

        with patch('dyn.tm.zones.Zone.add_record') as add_mock:
            with patch('dyn.tm.records.DNSRecord.delete') as delete_mock:
                with patch('dyn.tm.zones.Zone._update') as update_mock:
                    plan = provider.plan(new)
                    provider.apply(plan)
                    update_mock.assert_called()
                    self.assertTrue(plan.exists)
                # we expect 4 deletes, 2 from actual deletes and 2 from
                # updates which delete and recreate
                self.assertEquals(4, len(delete_mock.call_args_list))
            # the 2 (re)creates
            self.assertEquals(2, len(add_mock.call_args_list))
        execute_mock.assert_has_calls([
            call('/AllRecord/unit.tests/unit.tests./', 'GET', {'detail': 'Y'})
        ])
        self.assertEquals(3, len(plan.changes))


class TestDynProviderGeo(TestCase):

    with open('./tests/fixtures/dyn-traffic-director-get.json') as fh:
        traffic_director_response = loads(fh.read())

    @property
    def traffic_directors_response(self):
        return {
            'data': [{
                'active': 'Y',
                'label': 'unit.tests.:A',
                'nodes': [],
                'notifiers': [],
                'pending_change': '',
                'rulesets': [],
                'service_id': '2ERWXQNsb_IKG2YZgYqkPvk0PBM',
                'ttl': '300'
            }, {
                'active': 'Y',
                'label': 'some.other.:A',
                'nodes': [],
                'notifiers': [],
                'pending_change': '',
                'rulesets': [],
                'service_id': '3ERWXQNsb_IKG2YZgYqkPvk0PBM',
                'ttl': '300'
            }, {
                'active': 'Y',
                'label': 'other format',
                'nodes': [],
                'notifiers': [],
                'pending_change': '',
                'rulesets': [],
                'service_id': '4ERWXQNsb_IKG2YZgYqkPvk0PBM',
                'ttl': '300'
            }]
        }

    # Doing this as a property so that we get a fresh copy each time, dyn's
    # client lib messes with the return value and prevents it from working on
    # subsequent uses otherwise
    @property
    def records_response(self):
        return {
            'data': {
                'a_records': [{
                    'fqdn': 'unit.tests',
                    'rdata': {'address': '1.2.3.4'},
                    'record_id': 1,
                    'record_type': 'A',
                    'ttl': 301,
                    'zone': 'unit.tests',
                }],
            }
        }

    monitor_id = '42a'
    monitors_response = {
        'data': [{
            'active': 'Y',
            'agent_scheme': 'geo',
            'dsf_monitor_id': monitor_id,
            'endpoints': [],
            'label': 'unit.tests.:A',
            'notifier': [],
            'expected': '',
            'header': 'User-Agent: Dyn Monitor',
            'host': 'unit.tests',
            'path': '/_dns',
            'port': '443',
            'timeout': '10',
            'probe_interval': '60',
            'protocol': 'HTTPS',
            'response_count': '2',
            'retries': '2',
            'services': ['12311']
        }, {
            'active': 'Y',
            'agent_scheme': 'geo',
            'dsf_monitor_id': 'b52',
            'endpoints': [],
            'label': 'old-label.unit.tests.',
            'notifier': [],
            'expected': '',
            'header': 'User-Agent: Dyn Monitor',
            'host': 'old-label.unit.tests',
            'path': '/_dns',
            'port': '443',
            'timeout': '10',
            'probe_interval': '60',
            'protocol': 'HTTPS',
            'response_count': '2',
            'retries': '2',
            'services': ['12312']
        }],
        'job_id': 3376281406,
        'msgs': [{
            'ERR_CD': None,
            'INFO': 'DSFMonitor_get: Here are your monitors',
            'LVL': 'INFO',
            'SOURCE': 'BLL'
        }],
        'status': 'success'
    }

    expected_geo = Zone('unit.tests.', [])
    geo_record = Record.new(expected_geo, '', {
        'geo': {
            'AF': ['2.2.3.4', '2.2.3.5'],
            'AS-JP': ['3.2.3.4', '3.2.3.5'],
            'NA-US': ['4.2.3.4', '4.2.3.5'],
            'NA-US-CA': ['5.2.3.4', '5.2.3.5']
        },
        'ttl': 300,
        'type': 'A',
        'values': ['1.2.3.4', '1.2.3.5'],
    })
    expected_geo.add_record(geo_record)
    expected_regular = Zone('unit.tests.', [])
    regular_record = Record.new(expected_regular, '', {
        'ttl': 301,
        'type': 'A',
        'value': '1.2.3.4',
    })
    expected_regular.add_record(regular_record)

    def setUp(self):
        # Flush our zone to ensure we start fresh
        _CachingDynZone.flush_zone('unit.tests')

    @patch('dyn.core.SessionEngine.execute')
    def test_traffic_directors(self, mock):
        provider = DynProvider('test', 'cust', 'user', 'pass', True)
        # short-circuit session checking
        provider._dyn_sess = True
        provider.log.warn = MagicMock()

        # no tds
        mock.side_effect = [{'data': []}]
        self.assertEquals({}, provider.traffic_directors)

        # a supported td and an ignored one
        response = {
            'data': [{
                'active': 'Y',
                'label': 'unit.tests.:A',
                'nodes': [],
                'notifiers': [],
                'pending_change': '',
                'rulesets': [],
                'service_id': '2ERWXQNsb_IKG2YZgYqkPvk0PBM',
                'ttl': '300'
            }, {
                'active': 'Y',
                'label': 'geo.unit.tests.:A',
                'nodes': [],
                'notifiers': [],
                'pending_change': '',
                'rulesets': [],
                'service_id': '3ERWXQNsb_IKG2YZgYqkPvk0PBM',
                'ttl': '300'
            }, {
                'active': 'Y',
                'label': 'something else',
                'nodes': [],
                'notifiers': [],
                'pending_change': '',
                'rulesets': [],
                'service_id': '4ERWXQNsb_IKG2YZgYqkPvk0PBM',
                'ttl': '300'
            }],
            'job_id': 3376164583,
            'status': 'success'
        }
        mock.side_effect = [response]
        # first make sure that we get the empty version from cache
        self.assertEquals({}, provider.traffic_directors)
        # reach in and bust the cache
        provider._traffic_directors = None
        tds = provider.traffic_directors
        self.assertEquals(set(['unit.tests.', 'geo.unit.tests.']),
                          set(tds.keys()))
        self.assertEquals(['A'], tds['unit.tests.'].keys())
        self.assertEquals(['A'], tds['geo.unit.tests.'].keys())
        provider.log.warn.assert_called_with("Failed to load TrafficDirector "
                                             "'%s': %s", 'something else',
                                             'need more than 1 value to '
                                             'unpack')

    @patch('dyn.core.SessionEngine.execute')
    def test_traffic_director_monitor(self, mock):
        provider = DynProvider('test', 'cust', 'user', 'pass', True)
        # short-circuit session checking
        provider._dyn_sess = True
        existing = Zone('unit.tests.', [])

        # no monitors, will try and create
        geo_monitor_id = '42x'
        mock.side_effect = [self.monitors_response, {
            'data': {
                'active': 'Y',
                'dsf_monitor_id': geo_monitor_id,
                'endpoints': [],
                'label': 'geo.unit.tests.:A',
                'notifier': '',
                'expected': '',
                'header': 'User-Agent: Dyn Monitor',
                'host': 'geo.unit.tests.',
                'path': '/_dns',
                'port': '443',
                'timeout': '10',
                'probe_interval': '60',
                'protocol': 'HTTPS',
                'response_count': '2',
                'retries': '2'
            },
            'job_id': 3376259461,
            'msgs': [{'ERR_CD': None,
                      'INFO': 'add: Here is the new monitor',
                      'LVL': 'INFO',
                      'SOURCE': 'BLL'}],
            'status': 'success'
        }]

        # ask for a monitor that doesn't exist
        record = Record.new(existing, 'geo', {
            'ttl': 60,
            'type': 'A',
            'value': '1.2.3.4',
            'octodns': {
                'healthcheck': {
                    'host': 'foo.bar',
                    'path': '/_ready'
                }
            }
        })
        monitor = provider._traffic_director_monitor(record)
        self.assertEquals(geo_monitor_id, monitor.dsf_monitor_id)
        # should see a request for the list and a create
        mock.assert_has_calls([
            call('/DSFMonitor/', 'GET', {'detail': 'Y'}),
            call('/DSFMonitor/', 'POST', {
                'retries': 2,
                'protocol': 'HTTPS',
                'response_count': 2,
                'label': 'geo.unit.tests.:A',
                'probe_interval': 60,
                'active': 'Y',
                'options': {
                    'path': '/_ready',
                    'host': 'foo.bar',
                    'header': 'User-Agent: Dyn Monitor',
                    'port': 443,
                    'timeout': 10
                }
            })
        ])
        # created monitor is now cached
        self.assertTrue('geo.unit.tests.:A' in
                        provider._traffic_director_monitors)
        # pre-existing one is there too
        self.assertTrue('unit.tests.:A' in
                        provider._traffic_director_monitors)

        # now ask for a monitor that does exist
        record = Record.new(existing, '', {
            'ttl': 60,
            'type': 'A',
            'value': '1.2.3.4'
        })
        mock.reset_mock()
        monitor = provider._traffic_director_monitor(record)
        self.assertEquals(self.monitor_id, monitor.dsf_monitor_id)
        # should have resulted in no calls b/c exists & we've cached the list
        mock.assert_not_called()

        # and finally for a monitor that exists, but with a differing config
        record = Record.new(existing, '', {
            'octodns': {
                'healthcheck': {
                    'host': 'bleep.bloop',
                    'path': '/_nope',
                    'protocol': 'HTTP',
                    'port': 8080,
                }
            },
            'ttl': 60,
            'type': 'A',
            'value': '1.2.3.4'
        })
        mock.reset_mock()
        mock.side_effect = [{
            'data': {
                'active': 'Y',
                'dsf_monitor_id': self.monitor_id,
                'endpoints': [],
                'label': 'unit.tests.:A',
                'notifier': '',
                'expected': '',
                'header': 'User-Agent: Dyn Monitor',
                'host': 'bleep.bloop',
                'path': '/_nope',
                'port': '8080',
                'timeout': '10',
                'probe_interval': '60',
                'protocol': 'HTTP',
                'response_count': '2',
                'retries': '2'
            },
            'job_id': 3376259461,
            'msgs': [{'ERR_CD': None,
                      'INFO': 'add: Here is the new monitor',
                      'LVL': 'INFO',
                      'SOURCE': 'BLL'}],
            'status': 'success'
        }]
        monitor = provider._traffic_director_monitor(record)
        self.assertEquals(self.monitor_id, monitor.dsf_monitor_id)
        # should have resulted an update
        mock.assert_has_calls([
            call('/DSFMonitor/42a/', 'PUT', {
                'protocol': 'HTTP',
                'options': {
                    'path': '/_nope',
                    'host': 'bleep.bloop',
                    'header': 'User-Agent: Dyn Monitor',
                    'port': 8080,
                    'timeout': 10
                }
            })
        ])
        # cached monitor should have been updated
        self.assertTrue('unit.tests.:A' in
                        provider._traffic_director_monitors)
        monitor = provider._traffic_director_monitors['unit.tests.:A']
        self.assertEquals('bleep.bloop', monitor.host)
        self.assertEquals('/_nope', monitor.path)
        self.assertEquals('HTTP', monitor.protocol)
        self.assertEquals('8080', monitor.port)

        # test upgrading an old label
        record = Record.new(existing, 'old-label', {
            'ttl': 60,
            'type': 'A',
            'value': '1.2.3.4'
        })
        mock.reset_mock()
        mock.side_effect = [{
            'data': {
                'active': 'Y',
                'dsf_monitor_id': self.monitor_id,
                'endpoints': [],
                'label': 'old-label.unit.tests.:A',
                'notifier': '',
                'expected': '',
                'header': 'User-Agent: Dyn Monitor',
                'host': 'old-label.unit.tests',
                'path': '/_dns',
                'port': '443',
                'timeout': '10',
                'probe_interval': '60',
                'protocol': 'HTTPS',
                'response_count': '2',
                'retries': '2'
            },
            'job_id': 3376259461,
            'msgs': [{'ERR_CD': None,
                      'INFO': 'add: Here is the new monitor',
                      'LVL': 'INFO',
                      'SOURCE': 'BLL'}],
            'status': 'success'
        }]
        monitor = provider._traffic_director_monitor(record)
        self.assertEquals(self.monitor_id, monitor.dsf_monitor_id)
        # should have resulted an update
        mock.assert_has_calls([
            call('/DSFMonitor/b52/', 'PUT', {
                'label': 'old-label.unit.tests.:A'
            })
        ])
        # cached monitor should have been updated
        self.assertTrue('old-label.unit.tests.:A' in
                        provider._traffic_director_monitors)

    @patch('dyn.core.SessionEngine.execute')
    def test_extra_changes(self, mock):
        provider = DynProvider('test', 'cust', 'user', 'pass', True)
        # short-circuit session checking
        provider._dyn_sess = True

        mock.side_effect = [self.monitors_response]

        # non-geo
        desired = Zone('unit.tests.', [])
        record = Record.new(desired, '', {
            'ttl': 60,
            'type': 'A',
            'value': '1.2.3.4',
        })
        desired.add_record(record)
        extra = provider._extra_changes(desired=desired,
                                        changes=[Create(record)])
        self.assertEquals(0, len(extra))

        # in changes, noop
        desired = Zone('unit.tests.', [])
        record = Record.new(desired, '', {
            'geo': {
                'NA': ['1.2.3.4'],
            },
            'ttl': 60,
            'type': 'A',
            'value': '1.2.3.4',
        })
        desired.add_record(record)
        extra = provider._extra_changes(desired=desired,
                                        changes=[Create(record)])
        self.assertEquals(0, len(extra))

        # no diff, no extra
        extra = provider._extra_changes(desired=desired, changes=[])
        self.assertEquals(0, len(extra))

        # monitors should have been fetched now
        mock.assert_called_once()

        # diff in healthcheck, gets extra
        desired = Zone('unit.tests.', [])
        record = Record.new(desired, '', {
            'geo': {
                'NA': ['1.2.3.4'],
            },
            'octodns': {
                'healthcheck': {
                    'host': 'foo.bar',
                    'path': '/_ready'
                }
            },
            'ttl': 60,
            'type': 'A',
            'value': '1.2.3.4',
        })
        desired.add_record(record)
        extra = provider._extra_changes(desired=desired, changes=[])
        self.assertEquals(1, len(extra))
        extra = extra[0]
        self.assertIsInstance(extra, Update)
        self.assertEquals(record, extra.record)

        # missing health check
        desired = Zone('unit.tests.', [])
        record = Record.new(desired, 'geo', {
            'geo': {
                'NA': ['1.2.3.4'],
            },
            'ttl': 60,
            'type': 'A',
            'value': '1.2.3.4',
        })
        desired.add_record(record)
        extra = provider._extra_changes(desired=desired, changes=[])
        self.assertEquals(1, len(extra))
        extra = extra[0]
        self.assertIsInstance(extra, Update)
        self.assertEquals(record, extra.record)

    @patch('dyn.core.SessionEngine.execute')
    def test_populate_traffic_directors_empty(self, mock):
        provider = DynProvider('test', 'cust', 'user', 'pass',
                               traffic_directors_enabled=True)

        # empty all around
        mock.side_effect = [
            # get traffic directors
            {'data': []},
            # get zone
            {'data': {}},
            # get records
            {'data': {}},
        ]
        got = Zone('unit.tests.', [])
        provider.populate(got)
        self.assertEquals(0, len(got.records))
        mock.assert_has_calls([
            call('/DSF/', 'GET', {'detail': 'Y'}),
            call('/Zone/unit.tests/', 'GET', {}),
            call('/AllRecord/unit.tests/unit.tests./', 'GET', {'detail': 'Y'}),
        ])

    @patch('dyn.core.SessionEngine.execute')
    def test_populate_traffic_directors_td(self, mock):
        provider = DynProvider('test', 'cust', 'user', 'pass',
                               traffic_directors_enabled=True)

        # only traffic director
        mock.side_effect = [
            # get traffic directors
            self.traffic_directors_response,
            # get traffic director
            self.traffic_director_response,
            # get zone
            {'data': {}},
            # get records
            {'data': {}},
        ]
        got = Zone('unit.tests.', [])
        provider.populate(got)
        self.assertEquals(1, len(got.records))
        self.assertFalse(self.expected_geo.changes(got, provider))
        mock.assert_has_calls([
            call('/DSF/2ERWXQNsb_IKG2YZgYqkPvk0PBM/', 'GET',
                 {'pending_changes': 'Y'}),
            call('/Zone/unit.tests/', 'GET', {}),
            call('/AllRecord/unit.tests/unit.tests./', 'GET', {'detail': 'Y'}),
        ])

    @patch('dyn.core.SessionEngine.execute')
    def test_populate_traffic_directors_regular(self, mock):
        provider = DynProvider('test', 'cust', 'user', 'pass',
                               traffic_directors_enabled=True)

        # only regular
        mock.side_effect = [
            # get traffic directors
            {'data': []},
            # get zone
            {'data': {}},
            # get records
            self.records_response
        ]
        got = Zone('unit.tests.', [])
        provider.populate(got)
        self.assertEquals(1, len(got.records))
        self.assertFalse(self.expected_regular.changes(got, provider))
        mock.assert_has_calls([
            call('/DSF/', 'GET', {'detail': 'Y'}),
            call('/Zone/unit.tests/', 'GET', {}),
            call('/AllRecord/unit.tests/unit.tests./', 'GET', {'detail': 'Y'}),
        ])

    @patch('dyn.core.SessionEngine.execute')
    def test_populate_traffic_directors_both(self, mock):
        provider = DynProvider('test', 'cust', 'user', 'pass',
                               traffic_directors_enabled=True)

        # both traffic director and regular, regular is ignored
        mock.side_effect = [
            # get traffic directors
            self.traffic_directors_response,
            # get traffic director
            self.traffic_director_response,
            # get zone
            {'data': {}},
            # get records
            self.records_response
        ]
        got = Zone('unit.tests.', [])
        provider.populate(got)
        self.assertEquals(1, len(got.records))
        self.assertFalse(self.expected_geo.changes(got, provider))
        mock.assert_has_calls([
            call('/DSF/2ERWXQNsb_IKG2YZgYqkPvk0PBM/', 'GET',
                 {'pending_changes': 'Y'}),
            call('/Zone/unit.tests/', 'GET', {}),
            call('/AllRecord/unit.tests/unit.tests./', 'GET', {'detail': 'Y'}),
        ])

    @patch('dyn.core.SessionEngine.execute')
    def test_populate_traffic_director_busted(self, mock):
        provider = DynProvider('test', 'cust', 'user', 'pass',
                               traffic_directors_enabled=True)

        busted_traffic_director_response = {
            "status": "success",
            "data": {
                "notifiers": [],
                "rulesets": [],
                "ttl": "300",
                "active": "Y",
                "service_id": "oIRZ4lM-W64NUelJGuzuVziZ4MI",
                "nodes": [{
                    "fqdn": "unit.tests",
                    "zone": "unit.tests"
                }],
                "pending_change": "",
                "label": "unit.tests.:A"
            },
            "job_id": 3376642606,
            "msgs": [{
                "INFO": "detail: Here is your service",
                "LVL": "INFO",
                "ERR_CD": None,
                "SOURCE": "BLL"
            }]
        }
        # busted traffic director
        mock.side_effect = [
            # get traffic directors
            self.traffic_directors_response,
            # get traffic director
            busted_traffic_director_response,
            # get zone
            {'data': {}},
            # get records
            {'data': {}},
        ]
        got = Zone('unit.tests.', [])
        provider.populate(got)
        self.assertEquals(1, len(got.records))
        # we expect a change here for the record, the values aren't important,
        # so just compare set contents (which does name and type)
        self.assertEquals(self.expected_geo.records, got.records)
        mock.assert_has_calls([
            call('/DSF/2ERWXQNsb_IKG2YZgYqkPvk0PBM/', 'GET',
                 {'pending_changes': 'Y'}),
            call('/Zone/unit.tests/', 'GET', {}),
            call('/AllRecord/unit.tests/unit.tests./', 'GET', {'detail': 'Y'}),
        ])

    @patch('dyn.core.SessionEngine.execute')
    def test_apply_traffic_director(self, mock):
        provider = DynProvider('test', 'cust', 'user', 'pass',
                               traffic_directors_enabled=True)

        # stubbing these out to avoid a lot of messy mocking, they'll be tested
        # individually, we'll check for expected calls
        provider._mod_geo_Create = MagicMock()
        provider._mod_geo_Update = MagicMock()
        provider._mod_geo_Delete = MagicMock()
        provider._mod_Create = MagicMock()
        provider._mod_Update = MagicMock()
        provider._mod_Delete = MagicMock()

        # busted traffic director
        mock.side_effect = [
            # get zone
            {'data': {}},
            # accept publish
            {'data': {}},
        ]
        desired = Zone('unit.tests.', [])
        geo = self.geo_record
        regular = self.regular_record

        changes = [
            Create(geo),
            Create(regular),
            Update(geo, geo),
            Update(regular, regular),
            Delete(geo),
            Delete(regular),
        ]
        plan = Plan(None, desired, changes, True)
        provider._apply(plan)
        mock.assert_has_calls([
            call('/Zone/unit.tests/', 'GET', {}),
            call('/Zone/unit.tests/', 'PUT', {'publish': True})
        ])
        # should have seen 1 call to each
        provider._mod_geo_Create.assert_called_once()
        provider._mod_geo_Update.assert_called_once()
        provider._mod_geo_Delete.assert_called_once()
        provider._mod_Create.assert_called_once()
        provider._mod_Update.assert_called_once()
        provider._mod_Delete.assert_called_once()

    @patch('dyn.core.SessionEngine.execute')
    def test_mod_geo_create(self, mock):
        provider = DynProvider('test', 'cust', 'user', 'pass',
                               traffic_directors_enabled=True)

        # will be tested separately
        provider._mod_rulesets = MagicMock()

        mock.side_effect = [
            # create traffic director
            self.traffic_director_response,
            # get traffic directors
            self.traffic_directors_response
        ]
        provider._mod_geo_Create(None, Create(self.geo_record))
        # td now lives in cache
        self.assertTrue('A' in provider.traffic_directors['unit.tests.'])
        # should have seen 1 gen call
        provider._mod_rulesets.assert_called_once()

    def test_mod_geo_update_geo_geo(self):
        provider = DynProvider('test', 'cust', 'user', 'pass',
                               traffic_directors_enabled=True)

        # update of an existing td

        # pre-populate the cache with our mock td
        provider._traffic_directors = {
            'unit.tests.': {
                'A': 42,
            }
        }
        # mock _mod_rulesets
        provider._mod_rulesets = MagicMock()

        geo = self.geo_record
        change = Update(geo, geo)
        provider._mod_geo_Update(None, change)
        # still in cache
        self.assertTrue('A' in provider.traffic_directors['unit.tests.'])
        # should have seen 1 gen call
        provider._mod_rulesets.assert_called_once_with(42, change)

    @patch('dyn.core.SessionEngine.execute')
    def test_mod_geo_update_geo_regular(self, _):
        provider = DynProvider('test', 'cust', 'user', 'pass',
                               traffic_directors_enabled=True)

        # convert a td to a regular record

        provider._mod_Create = MagicMock()
        provider._mod_geo_Delete = MagicMock()

        change = Update(self.geo_record, self.regular_record)
        provider._mod_geo_Update(42, change)
        # should have seen a call to create the new regular record
        provider._mod_Create.assert_called_once_with(42, change)
        # should have seen a call to delete the old td record
        provider._mod_geo_Delete.assert_called_once_with(42, change)

    @patch('dyn.core.SessionEngine.execute')
    def test_mod_geo_update_regular_geo(self, _):
        provider = DynProvider('test', 'cust', 'user', 'pass',
                               traffic_directors_enabled=True)

        # convert a regular record to a td

        provider._mod_geo_Create = MagicMock()
        provider._mod_Delete = MagicMock()

        change = Update(self.regular_record, self.geo_record)
        provider._mod_geo_Update(42, change)
        # should have seen a call to create the new geo record
        provider._mod_geo_Create.assert_called_once_with(42, change)
        # should have seen a call to delete the old regular record
        provider._mod_Delete.assert_called_once_with(42, change)

    @patch('dyn.core.SessionEngine.execute')
    def test_mod_geo_delete(self, mock):
        provider = DynProvider('test', 'cust', 'user', 'pass',
                               traffic_directors_enabled=True)

        td_mock = MagicMock()
        provider._traffic_directors = {
            'unit.tests.': {
                'A': td_mock,
            }
        }
        provider._mod_geo_Delete(None, Delete(self.geo_record))
        # delete called
        td_mock.delete.assert_called_once()
        # removed from cache
        self.assertFalse('A' in provider.traffic_directors['unit.tests.'])

    @patch('dyn.tm.services.DSFResponsePool.create')
    def test_find_or_create_pool(self, mock):
        provider = DynProvider('test', 'cust', 'user', 'pass',
                               traffic_directors_enabled=True)

        td = 42

        # no candidates cache miss, so create
        values = ['1.2.3.4', '1.2.3.5']
        pool = provider._find_or_create_pool(td, [], 'default', 'A', values)
        self.assertIsInstance(pool, DSFResponsePool)
        self.assertEquals(1, len(pool.rs_chains))
        records = pool.rs_chains[0].record_sets[0].records
        self.assertEquals(values, [r.address for r in records])
        mock.assert_called_once_with(td)

        # cache hit, use the one we just created
        mock.reset_mock()
        pools = [pool]
        cached = provider._find_or_create_pool(td, pools, 'default', 'A',
                                               values)
        self.assertEquals(pool, cached)
        mock.assert_not_called()

        # cache miss, non-matching label
        mock.reset_mock()
        miss = provider._find_or_create_pool(td, pools, 'NA-US-CA', 'A',
                                             values)
        self.assertNotEquals(pool, miss)
        self.assertEquals('NA-US-CA', miss.label)
        mock.assert_called_once_with(td)

        # cache miss, non-matching label
        mock.reset_mock()
        values = ['2.2.3.4.', '2.2.3.5']
        miss = provider._find_or_create_pool(td, pools, 'default', 'A', values)
        self.assertNotEquals(pool, miss)
        mock.assert_called_once_with(td)

    @patch('dyn.tm.services.DSFRuleset.add_response_pool')
    @patch('dyn.tm.services.DSFRuleset.create')
    # just lets us ignore the pool.create calls
    @patch('dyn.tm.services.DSFResponsePool.create')
    def test_mod_rulesets_create(self, _, ruleset_create_mock,
                                 add_response_pool_mock):
        provider = DynProvider('test', 'cust', 'user', 'pass',
                               traffic_directors_enabled=True)

        td_mock = MagicMock()
        td_mock._rulesets = []
        provider._traffic_director_monitor = MagicMock()
        provider._find_or_create_pool = MagicMock()

        td_mock.all_response_pools = []

        provider._find_or_create_pool.side_effect = [
            _DummyPool('default'),
            _DummyPool(1),
            _DummyPool(2),
            _DummyPool(3),
            _DummyPool(4),
        ]

        change = Create(self.geo_record)
        provider._mod_rulesets(td_mock, change)
        ruleset_create_mock.assert_has_calls((
            call(td_mock, index=0),
            call(td_mock, index=0),
            call(td_mock, index=0),
            call(td_mock, index=0),
            call(td_mock, index=0),
        ))
        add_response_pool_mock.assert_has_calls((
            # default
            call('default'),
            # first geo and it's fallback
            call(1),
            call('default', index=999),
            # 2nd geo and it's fallback
            call(2),
            call('default', index=999),
            # 3nd geo and it's fallback
            call(3),
            call('default', index=999),
            # 4th geo and it's 2 levels of fallback
            call(4),
            call(3, index=999),
            call('default', index=999),
        ))

    # have to patch the place it's imported into, not where it lives
    @patch('octodns.provider.dyn.get_response_pool')
    @patch('dyn.tm.services.DSFRuleset.add_response_pool')
    @patch('dyn.tm.services.DSFRuleset.create')
    # just lets us ignore the pool.create calls
    @patch('dyn.tm.services.DSFResponsePool.create')
    def test_mod_rulesets_existing(self, _, ruleset_create_mock,
                                   add_response_pool_mock,
                                   get_response_pool_mock):
        provider = DynProvider('test', 'cust', 'user', 'pass',
                               traffic_directors_enabled=True)

        ruleset_mock = MagicMock()
        ruleset_mock.response_pools = [_DummyPool(3)]

        td_mock = MagicMock()
        td_mock._rulesets = [
            ruleset_mock,
        ]
        provider._traffic_director_monitor = MagicMock()
        provider._find_or_create_pool = MagicMock()

        unused_pool = _DummyPool('unused')
        td_mock.all_response_pools = \
            ruleset_mock.response_pools + [unused_pool]
        get_response_pool_mock.return_value = unused_pool

        provider._find_or_create_pool.side_effect = [
            _DummyPool('default'),
            _DummyPool(1),
            _DummyPool(2),
            ruleset_mock.response_pools[0],
            _DummyPool(4),
        ]

        change = Create(self.geo_record)
        provider._mod_rulesets(td_mock, change)
        ruleset_create_mock.assert_has_calls((
            call(td_mock, index=2),
            call(td_mock, index=2),
            call(td_mock, index=2),
            call(td_mock, index=2),
            call(td_mock, index=2),
        ))
        add_response_pool_mock.assert_has_calls((
            # default
            call('default'),
            # first geo and it's fallback
            call(1),
            call('default', index=999),
            # 2nd geo and it's fallback
            call(2),
            call('default', index=999),
            # 3nd geo, from existing, and it's fallback
            call(3),
            call('default', index=999),
            # 4th geo and it's 2 levels of fallback
            call(4),
            call(3, index=999),
            call('default', index=999),
        ))
        # unused poll should have been deleted
        self.assertTrue(unused_pool.deleted)
        # old ruleset ruleset should be deleted, it's pool will have been
        # reused
        ruleset_mock.delete.assert_called_once()


class TestDynProviderAlias(TestCase):
    expected = Zone('unit.tests.', [])
    for name, data in (
            ('', {
                'type': 'ALIAS',
                'ttl': 300,
                'value': 'www.unit.tests.'
            }),
            ('www', {
                'type': 'A',
                'ttl': 300,
                'values': ['1.2.3.4']
            })):
        expected.add_record(Record.new(expected, name, data))

    def setUp(self):
        # Flush our zone to ensure we start fresh
        _CachingDynZone.flush_zone(self.expected.name[:-1])

    @patch('dyn.core.SessionEngine.execute')
    def test_populate(self, execute_mock):
        provider = DynProvider('test', 'cust', 'user', 'pass')

        # Test Zone create
        execute_mock.side_effect = [
            # get Zone
            {'data': {}},
            # get_all_records
            {'data': {
                'a_records': [{
                    'fqdn': 'www.unit.tests',
                    'rdata': {'address': '1.2.3.4'},
                    'record_id': 1,
                    'record_type': 'A',
                    'ttl': 300,
                    'zone': 'unit.tests',
                }],
                'alias_records': [{
                    'fqdn': 'unit.tests',
                    'rdata': {'alias': 'www.unit.tests.'},
                    'record_id': 2,
                    'record_type': 'ALIAS',
                    'ttl': 300,
                    'zone': 'unit.tests',
                }],
            }}
        ]
        got = Zone('unit.tests.', [])
        provider.populate(got)
        execute_mock.assert_has_calls([
            call('/Zone/unit.tests/', 'GET', {}),
            call('/AllRecord/unit.tests/unit.tests./', 'GET', {'detail': 'Y'})
        ])
        changes = self.expected.changes(got, SimpleProvider())
        self.assertEquals([], changes)

    @patch('dyn.core.SessionEngine.execute')
    def test_sync(self, execute_mock):
        provider = DynProvider('test', 'cust', 'user', 'pass')

        # Test Zone create
        execute_mock.side_effect = [
            # No such zone, during populate
            DynectGetError('foo'),
            # No such zone, during sync
            DynectGetError('foo'),
            # get empty Zone
            {'data': {}},
            # get zone we can modify & delete with
            {'data': {
                # A top-level to delete
                'a_records': [{
                    'fqdn': 'www.unit.tests',
                    'rdata': {'address': '1.2.3.4'},
                    'record_id': 1,
                    'record_type': 'A',
                    'ttl': 300,
                    'zone': 'unit.tests',
                }],
                # A node to delete
                'alias_records': [{
                    'fqdn': 'unit.tests',
                    'rdata': {'alias': 'www.unit.tests.'},
                    'record_id': 2,
                    'record_type': 'ALIAS',
                    'ttl': 300,
                    'zone': 'unit.tests',
                }],
            }}
        ]

        # No existing records, create all
        with patch('dyn.tm.zones.Zone.add_record') as add_mock:
            with patch('dyn.tm.zones.Zone._update') as update_mock:
                plan = provider.plan(self.expected)
                update_mock.assert_not_called()
                provider.apply(plan)
                update_mock.assert_called()
            add_mock.assert_called()
            # Once for each dyn record
            self.assertEquals(2, len(add_mock.call_args_list))
        execute_mock.assert_has_calls([call('/Zone/unit.tests/', 'GET', {}),
                                       call('/Zone/unit.tests/', 'GET', {})])
        self.assertEquals(2, len(plan.changes))


# Need a class that doesn't do all the "real" stuff, but gets our monkey
# patching
class DummyDSFMonitor(DSFMonitor):

    def __init__(self, host=None, path=None, protocol=None, port=None,
                 options_host=None, options_path=None, options_protocol=None,
                 options_port=None):
        # not calling super on purpose
        self._host = host
        self._path = path
        self._protocol = protocol
        self._port = port
        if options_host:
            self._options = {
                'host': options_host,
                'path': options_path,
                'protocol': options_protocol,
                'port': options_port,
            }
        else:
            self._options = None


class TestDSFMonitorMonkeyPatching(TestCase):

    def test_host(self):
        monitor = DummyDSFMonitor(host='host.com', path='/path',
                                  protocol='HTTP', port=8080)
        self.assertEquals('host.com', monitor.host)
        self.assertEquals('/path', monitor.path)
        self.assertEquals('HTTP', monitor.protocol)
        self.assertEquals(8080, monitor.port)

        monitor = DummyDSFMonitor(options_host='host.com',
                                  options_path='/path',
                                  options_protocol='HTTP', options_port=8080)
        self.assertEquals('host.com', monitor.host)
        self.assertEquals('/path', monitor.path)

        monitor.host = 'other.com'
        self.assertEquals('other.com', monitor.host)
        monitor.path = '/other-path'
        self.assertEquals('/other-path', monitor.path)
        monitor.protocol = 'HTTPS'
        self.assertEquals('HTTPS', monitor.protocol)
        monitor.port = 8081
        self.assertEquals(8081, monitor.port)

        monitor = DummyDSFMonitor()
        monitor.host = 'other.com'
        self.assertEquals('other.com', monitor.host)
        monitor = DummyDSFMonitor()
        monitor.path = '/other-path'
        self.assertEquals('/other-path', monitor.path)
        monitor.protocol = 'HTTP'
        self.assertEquals('HTTP', monitor.protocol)
        monitor.port = 8080
        self.assertEquals(8080, monitor.port)

        # Just to exercise the _options init
        monitor = DummyDSFMonitor()
        monitor.protocol = 'HTTP'
        self.assertEquals('HTTP', monitor.protocol)
        monitor = DummyDSFMonitor()
        monitor.port = 8080
        self.assertEquals(8080, monitor.port)
