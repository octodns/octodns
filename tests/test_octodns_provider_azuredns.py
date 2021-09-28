#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from octodns.record import Create, Update, Delete, Record
from octodns.provider.azuredns import _AzureRecord, AzureProvider, \
    _check_endswith_dot, _parse_azure_type, _root_traffic_manager_name, \
    _get_monitor, _profile_is_match, AzureException
from octodns.zone import Zone
from octodns.provider.base import Plan

from azure.mgmt.dns.models import ARecord, AaaaRecord, CaaRecord, \
    CnameRecord, MxRecord, SrvRecord, NsRecord, PtrRecord, TxtRecord, \
    RecordSet, SoaRecord, SubResource, Zone as AzureZone
from azure.mgmt.trafficmanager.models import Profile, DnsConfig, \
    MonitorConfig, Endpoint, MonitorConfigCustomHeadersItem
from msrestazure.azure_exceptions import CloudError

from unittest import TestCase
from mock import Mock, patch, call


zone = Zone(name='unit.tests.', sub_zones=[])
octo_records = []
octo_records.append(Record.new(zone, '', {
    'ttl': 0,
    'type': 'A',
    'values': ['1.2.3.4', '10.10.10.10']}))
octo_records.append(Record.new(zone, 'a', {
    'ttl': 1,
    'type': 'A',
    'values': ['1.2.3.4', '1.1.1.1']}))
octo_records.append(Record.new(zone, 'aa', {
    'ttl': 9001,
    'type': 'A',
    'values': ['1.2.4.3']}))
octo_records.append(Record.new(zone, 'aaa', {
    'ttl': 2,
    'type': 'A',
    'values': ['1.1.1.3']}))
octo_records.append(Record.new(zone, 'aaaa1', {
    'ttl': 300,
    'type': 'AAAA',
    'values': ['2601:644:500:e210:62f8:1dff:feb8:947a',
               '2601:642:500:e210:62f8:1dff:feb8:947a'],
}))
octo_records.append(Record.new(zone, 'aaaa2', {
    'ttl': 300,
    'type': 'AAAA',
    'value': '2601:644:500:e210:62f8:1dff:feb8:947a'
}))
octo_records.append(Record.new(zone, 'caa1', {
    'ttl': 9,
    'type': 'CAA',
    'value': {
        'flags': 0,
        'tag': 'issue',
        'value': 'ca.unit.tests',
    }}))
octo_records.append(Record.new(zone, 'caa2', {
    'ttl': 9,
    'type': 'CAA',
    'values': [{
        'flags': 0,
        'tag': 'issue',
        'value': 'ca1.unit.tests',
    }, {
        'flags': 0,
        'tag': 'issue',
        'value': 'ca2.unit.tests',
    }]}))
octo_records.append(Record.new(zone, 'cname', {
    'ttl': 3,
    'type': 'CNAME',
    'value': 'a.unit.tests.'}))
octo_records.append(Record.new(zone, 'mx1', {
    'ttl': 3,
    'type': 'MX',
    'values': [{
        'priority': 10,
        'value': 'mx1.unit.tests.',
    }, {
        'priority': 20,
        'value': 'mx2.unit.tests.',
    }]}))
octo_records.append(Record.new(zone, 'mx2', {
    'ttl': 3,
    'type': 'MX',
    'values': [{
        'priority': 10,
        'value': 'mx1.unit.tests.',
    }]}))
octo_records.append(Record.new(zone, '', {
    'ttl': 4,
    'type': 'NS',
    'values': ['ns1.unit.tests.', 'ns2.unit.tests.']}))
octo_records.append(Record.new(zone, 'foo', {
    'ttl': 5,
    'type': 'NS',
    'value': 'ns1.unit.tests.'}))
octo_records.append(Record.new(zone, 'ptr1', {
    'ttl': 5,
    'type': 'PTR',
    'value': 'ptr1.unit.tests.'}))
octo_records.append(Record.new(zone, '_srv._tcp', {
    'ttl': 6,
    'type': 'SRV',
    'values': [{
        'priority': 10,
        'weight': 20,
        'port': 30,
        'target': 'foo-1.unit.tests.',
    }, {
        'priority': 12,
        'weight': 30,
        'port': 30,
        'target': 'foo-2.unit.tests.',
    }]}))
octo_records.append(Record.new(zone, '_srv2._tcp', {
    'ttl': 7,
    'type': 'SRV',
    'values': [{
        'priority': 12,
        'weight': 17,
        'port': 1,
        'target': 'srvfoo.unit.tests.',
    }]}))
octo_records.append(Record.new(zone, 'txt1', {
    'ttl': 8,
    'type': 'TXT',
    'value': 'txt singleton test'}))
octo_records.append(Record.new(zone, 'txt2', {
    'ttl': 9,
    'type': 'TXT',
    'values': ['txt multiple test', 'txt multiple test 2']}))

long_txt = "v=spf1 ip4:10.10.0.0/24 ip4:10.10.1.0/24 ip4:10.10.2.0/24"
long_txt += " ip4:10.10.3.0/24 ip4:10.10.4.0/24 ip4:10.10.5.0/24 "
long_txt += " 10.6.0/24 ip4:10.10.7.0/24 ip4:10.10.8.0/24 "
long_txt += " ip4:10.10.10.0/24 ip4:10.10.11.0/24 ip4:10.10.12.0/24"
long_txt += " ip4:10.10.13.0/24 ip4:10.10.14.0/24 ip4:10.10.15.0/24"
long_txt += " ip4:10.10.16.0/24 ip4:10.10.17.0/24 ip4:10.10.18.0/24"
long_txt += " ip4:10.10.19.0/24 ip4:10.10.20.0/24  ~all"
octo_records.append(Record.new(zone, 'txt3', {
    'ttl': 10,
    'type': 'TXT',
    'values': ['txt multiple test', long_txt]}))

octo_records.append(Record.new(zone, 'ptr2', {
    'ttl': 11,
    'type': 'PTR',
    'values': ['ptr21.unit.tests.', 'ptr22.unit.tests.']}))

azure_records = []
_base0 = _AzureRecord('TestAzure', octo_records[0])
_base0.zone_name = 'unit.tests'
_base0.relative_record_set_name = '@'
_base0.record_type = 'A'
_base0.params['ttl'] = 0
_base0.params['a_records'] = [ARecord(ipv4_address='1.2.3.4'),
                              ARecord(ipv4_address='10.10.10.10')]
azure_records.append(_base0)

_base1 = _AzureRecord('TestAzure', octo_records[1])
_base1.zone_name = 'unit.tests'
_base1.relative_record_set_name = 'a'
_base1.record_type = 'A'
_base1.params['ttl'] = 1
_base1.params['a_records'] = [ARecord(ipv4_address='1.2.3.4'),
                              ARecord(ipv4_address='1.1.1.1')]
azure_records.append(_base1)

_base2 = _AzureRecord('TestAzure', octo_records[2])
_base2.zone_name = 'unit.tests'
_base2.relative_record_set_name = 'aa'
_base2.record_type = 'A'
_base2.params['ttl'] = 9001
_base2.params['a_records'] = ARecord(ipv4_address='1.2.4.3')
azure_records.append(_base2)

_base3 = _AzureRecord('TestAzure', octo_records[3])
_base3.zone_name = 'unit.tests'
_base3.relative_record_set_name = 'aaa'
_base3.record_type = 'A'
_base3.params['ttl'] = 2
_base3.params['a_records'] = ARecord(ipv4_address='1.1.1.3')
azure_records.append(_base3)

_base4 = _AzureRecord('TestAzure', octo_records[4])
_base4.zone_name = 'unit.tests'
_base4.relative_record_set_name = 'aaaa1'
_base4.record_type = 'AAAA'
_base4.params['ttl'] = 300
aaaa1 = AaaaRecord(ipv6_address='2601:644:500:e210:62f8:1dff:feb8:947a')
aaaa2 = AaaaRecord(ipv6_address='2601:642:500:e210:62f8:1dff:feb8:947a')
_base4.params['aaaa_records'] = [aaaa1, aaaa2]
azure_records.append(_base4)

_base5 = _AzureRecord('TestAzure', octo_records[5])
_base5.zone_name = 'unit.tests'
_base5.relative_record_set_name = 'aaaa2'
_base5.record_type = 'AAAA'
_base5.params['ttl'] = 300
_base5.params['aaaa_records'] = [aaaa1]
azure_records.append(_base5)

_base6 = _AzureRecord('TestAzure', octo_records[6])
_base6.zone_name = 'unit.tests'
_base6.relative_record_set_name = 'caa1'
_base6.record_type = 'CAA'
_base6.params['ttl'] = 9
_base6.params['caa_records'] = [CaaRecord(flags=0,
                                          tag='issue',
                                          value='ca.unit.tests')]
azure_records.append(_base6)

_base7 = _AzureRecord('TestAzure', octo_records[7])
_base7.zone_name = 'unit.tests'
_base7.relative_record_set_name = 'caa2'
_base7.record_type = 'CAA'
_base7.params['ttl'] = 9
_base7.params['caa_records'] = [CaaRecord(flags=0,
                                          tag='issue',
                                          value='ca1.unit.tests'),
                                CaaRecord(flags=0,
                                          tag='issue',
                                          value='ca2.unit.tests')]
azure_records.append(_base7)

_base8 = _AzureRecord('TestAzure', octo_records[8])
_base8.zone_name = 'unit.tests'
_base8.relative_record_set_name = 'cname'
_base8.record_type = 'CNAME'
_base8.params['ttl'] = 3
_base8.params['cname_record'] = CnameRecord(cname='a.unit.tests.')
azure_records.append(_base8)

_base9 = _AzureRecord('TestAzure', octo_records[9])
_base9.zone_name = 'unit.tests'
_base9.relative_record_set_name = 'mx1'
_base9.record_type = 'MX'
_base9.params['ttl'] = 3
_base9.params['mx_records'] = [MxRecord(preference=10,
                                        exchange='mx1.unit.tests.'),
                               MxRecord(preference=20,
                                        exchange='mx2.unit.tests.')]
azure_records.append(_base9)

_base10 = _AzureRecord('TestAzure', octo_records[10])
_base10.zone_name = 'unit.tests'
_base10.relative_record_set_name = 'mx2'
_base10.record_type = 'MX'
_base10.params['ttl'] = 3
_base10.params['mx_records'] = [MxRecord(preference=10,
                                         exchange='mx1.unit.tests.')]
azure_records.append(_base10)

_base11 = _AzureRecord('TestAzure', octo_records[11])
_base11.zone_name = 'unit.tests'
_base11.relative_record_set_name = '@'
_base11.record_type = 'NS'
_base11.params['ttl'] = 4
_base11.params['ns_records'] = [NsRecord(nsdname='ns1.unit.tests.'),
                                NsRecord(nsdname='ns2.unit.tests.')]
azure_records.append(_base11)

_base12 = _AzureRecord('TestAzure', octo_records[12])
_base12.zone_name = 'unit.tests'
_base12.relative_record_set_name = 'foo'
_base12.record_type = 'NS'
_base12.params['ttl'] = 5
_base12.params['ns_records'] = [NsRecord(nsdname='ns1.unit.tests.')]
azure_records.append(_base12)

_base13 = _AzureRecord('TestAzure', octo_records[13])
_base13.zone_name = 'unit.tests'
_base13.relative_record_set_name = 'ptr1'
_base13.record_type = 'PTR'
_base13.params['ttl'] = 5
_base13.params['ptr_records'] = [PtrRecord(ptrdname='ptr1.unit.tests.')]
azure_records.append(_base13)

_base14 = _AzureRecord('TestAzure', octo_records[14])
_base14.zone_name = 'unit.tests'
_base14.relative_record_set_name = '_srv._tcp'
_base14.record_type = 'SRV'
_base14.params['ttl'] = 6
_base14.params['srv_records'] = [SrvRecord(priority=10,
                                           weight=20,
                                           port=30,
                                           target='foo-1.unit.tests.'),
                                 SrvRecord(priority=12,
                                           weight=30,
                                           port=30,
                                           target='foo-2.unit.tests.')]
azure_records.append(_base14)

_base15 = _AzureRecord('TestAzure', octo_records[15])
_base15.zone_name = 'unit.tests'
_base15.relative_record_set_name = '_srv2._tcp'
_base15.record_type = 'SRV'
_base15.params['ttl'] = 7
_base15.params['srv_records'] = [SrvRecord(priority=12,
                                           weight=17,
                                           port=1,
                                           target='srvfoo.unit.tests.')]
azure_records.append(_base15)

_base16 = _AzureRecord('TestAzure', octo_records[16])
_base16.zone_name = 'unit.tests'
_base16.relative_record_set_name = 'txt1'
_base16.record_type = 'TXT'
_base16.params['ttl'] = 8
_base16.params['txt_records'] = [TxtRecord(value=['txt singleton test'])]
azure_records.append(_base16)

_base17 = _AzureRecord('TestAzure', octo_records[17])
_base17.zone_name = 'unit.tests'
_base17.relative_record_set_name = 'txt2'
_base17.record_type = 'TXT'
_base17.params['ttl'] = 9
_base17.params['txt_records'] = [TxtRecord(value=['txt multiple test']),
                                 TxtRecord(value=['txt multiple test 2'])]
azure_records.append(_base17)

long_txt_az1 = "v=spf1 ip4:10.10.0.0/24 ip4:10.10.1.0/24 ip4:10.10.2.0/24"
long_txt_az1 += " ip4:10.10.3.0/24 ip4:10.10.4.0/24 ip4:10.10.5.0/24 "
long_txt_az1 += " 10.6.0/24 ip4:10.10.7.0/24 ip4:10.10.8.0/24 "
long_txt_az1 += " ip4:10.10.10.0/24 ip4:10.10.11.0/24 ip4:10.10.12.0/24"
long_txt_az1 += " ip4:10.10.13.0/24 ip4:10.10.14.0/24 ip4:10.10."
long_txt_az2 = "15.0/24 ip4:10.10.16.0/24 ip4:10.10.17.0/24 ip4:10.10.18.0/24"
long_txt_az2 += " ip4:10.10.19.0/24 ip4:10.10.20.0/24  ~all"
_base18 = _AzureRecord('TestAzure', octo_records[18])
_base18.zone_name = 'unit.tests'
_base18.relative_record_set_name = 'txt3'
_base18.record_type = 'TXT'
_base18.params['ttl'] = 10
_base18.params['txt_records'] = [TxtRecord(value=['txt multiple test']),
                                 TxtRecord(value=[long_txt_az1, long_txt_az2])]
azure_records.append(_base18)

_base19 = _AzureRecord('TestAzure', octo_records[19])
_base19.zone_name = 'unit.tests'
_base19.relative_record_set_name = 'ptr2'
_base19.record_type = 'PTR'
_base19.params['ttl'] = 11
_base19.params['ptr_records'] = [PtrRecord(ptrdname='ptr21.unit.tests.'),
                                 PtrRecord(ptrdname='ptr22.unit.tests.')]
azure_records.append(_base19)


class Test_AzureRecord(TestCase):
    def test_azure_record(self):
        assert(len(azure_records) == len(octo_records))
        for i in range(len(azure_records)):
            octo = _AzureRecord('TestAzure', octo_records[i])
            assert(azure_records[i]._equals(octo))


class Test_DynamicAzureRecord(TestCase):
    def test_azure_record(self):
        tm_profile = Profile()
        data = {
            'ttl': 60,
            'type': 'CNAME',
            'value': 'default.unit.tests.',
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [
                            {'value': 'one.unit.tests.', 'weight': 1}
                        ],
                        'fallback': 'two',
                    },
                    'two': {
                        'values': [
                            {'value': 'two.unit.tests.', 'weight': 1}
                        ],
                    },
                },
                'rules': [
                    {'geos': ['AF'], 'pool': 'one'},
                    {'pool': 'two'},
                ],
            }
        }
        octo_record = Record.new(zone, 'foo', data)
        azure_record = _AzureRecord('TestAzure', octo_record,
                                    traffic_manager=tm_profile)
        self.assertEqual(azure_record.zone_name, zone.name[:-1])
        self.assertEqual(azure_record.relative_record_set_name, 'foo')
        self.assertEqual(azure_record.record_type, 'CNAME')
        self.assertEqual(azure_record.params['ttl'], 60)
        self.assertEqual(azure_record.params['target_resource'], tm_profile)


class Test_ParseAzureType(TestCase):
    def test_parse_azure_type(self):
        for expected, test in [['A', 'Microsoft.Network/dnszones/A'],
                               ['AAAA', 'Microsoft.Network/dnszones/AAAA'],
                               ['NS', 'Microsoft.Network/dnszones/NS'],
                               ['MX', 'Microsoft.Network/dnszones/MX']]:
            self.assertEquals(expected, _parse_azure_type(test))


class Test_CheckEndswithDot(TestCase):
    def test_check_endswith_dot(self):
        for expected, test in [['a.', 'a'],
                               ['a.', 'a.'],
                               ['foo.bar.', 'foo.bar.'],
                               ['foo.bar.', 'foo.bar']]:
            self.assertEquals(expected, _check_endswith_dot(test))


class Test_RootTrafficManagerName(TestCase):
    def test_root_traffic_manager_name(self):
        test = Record.new(zone, 'foo', data={
            'ttl': 60, 'type': 'CNAME', 'value': 'default.unit.tests.',
        })
        self.assertEqual(_root_traffic_manager_name(test), 'foo--unit--tests')


class Test_GetMonitor(TestCase):
    def test_get_monitor(self):
        record = Record.new(zone, 'foo', data={
            'type': 'CNAME', 'ttl': 60, 'value': 'default.unit.tests.',
            'octodns': {
                'healthcheck': {
                    'path': '/_ping',
                    'port': 4443,
                    'protocol': 'HTTPS',
                }
            },
        })

        monitor = _get_monitor(record)
        self.assertEqual(monitor.protocol, 'HTTPS')
        self.assertEqual(monitor.port, 4443)
        self.assertEqual(monitor.path, '/_ping')
        headers = monitor.custom_headers
        self.assertIsInstance(headers, list)
        self.assertEquals(len(headers), 1)
        headers = headers[0]
        self.assertEqual(headers.name, 'Host')
        self.assertEqual(headers.value, record.healthcheck_host())

        # test TCP monitor
        record._octodns['healthcheck']['protocol'] = 'TCP'
        monitor = _get_monitor(record)
        self.assertEqual(monitor.protocol, 'TCP')
        self.assertIsNone(monitor.custom_headers)


class Test_ProfileIsMatch(TestCase):
    def test_profile_is_match(self):
        is_match = _profile_is_match

        self.assertFalse(is_match(None, Profile()))

        # Profile object builder with default property values that can be
        # overridden for testing below
        def profile(
            name = 'foo-unit-tests',
            ttl = 60,
            method = 'Geographic',
            dns_name = None,
            monitor_proto = 'HTTPS',
            monitor_port = 4443,
            monitor_path = '/_ping',
            endpoints = 1,
            endpoint_name = 'name',
            endpoint_type = 'profile/nestedEndpoints',
            endpoint_status = None,
            target = 'target.unit.tests',
            target_id = 'resource/id',
            geos = ['GEO-AF'],
            weight = 1,
            priority = 1,
        ):
            dns = DnsConfig(relative_name=(dns_name or name), ttl=ttl)
            return Profile(
                name=name, traffic_routing_method=method, dns_config=dns,
                monitor_config=MonitorConfig(
                    protocol=monitor_proto,
                    port=monitor_port,
                    path=monitor_path,
                ),
                endpoints=[Endpoint(
                    name=endpoint_name,
                    type=endpoint_type,
                    endpoint_status=endpoint_status,
                    target=target,
                    target_resource_id=target_id,
                    geo_mapping=geos,
                    weight=weight,
                    priority=priority,
                )] + [Endpoint()] * (endpoints - 1),
            )

        self.assertTrue(is_match(profile(), profile()))

        self.assertFalse(is_match(profile(), profile(name='two')))
        self.assertFalse(is_match(profile(), profile(endpoints=2)))
        self.assertFalse(is_match(profile(), profile(dns_name='two')))
        self.assertFalse(is_match(profile(), profile(monitor_proto='HTTP')))
        self.assertFalse(is_match(profile(), profile(endpoint_name='a')))
        self.assertFalse(is_match(profile(), profile(endpoint_type='b')))
        self.assertFalse(
            is_match(profile(), profile(endpoint_status='Disabled'))
        )
        self.assertFalse(
            is_match(profile(endpoint_type='b'), profile(endpoint_type='b'))
        )
        self.assertFalse(is_match(profile(), profile(target_id='rsrc/id2')))
        self.assertFalse(is_match(profile(), profile(geos=['IN'])))

        def wprofile(**kwargs):
            kwargs['method'] = 'Weighted'
            kwargs['endpoint_type'] = 'profile/externalEndpoints'
            return profile(**kwargs)

        self.assertFalse(is_match(wprofile(), wprofile(target='bar.unit')))
        self.assertFalse(is_match(wprofile(), wprofile(weight=3)))


class TestAzureDnsProvider(TestCase):
    def _provider(self):
        return self._get_provider('mock_spc', 'mock_dns_client')

    @patch('octodns.provider.azuredns.TrafficManagerManagementClient')
    @patch('octodns.provider.azuredns.DnsManagementClient')
    @patch('octodns.provider.azuredns.ClientSecretCredential')
    @patch('octodns.provider.azuredns.ServicePrincipalCredentials')
    def _get_provider(self, mock_spc, mock_css, mock_dns_client,
                      mock_tm_client):
        '''Returns a mock AzureProvider object to use in testing.

            :param mock_spc: placeholder
            :type  mock_spc: str
            :param mock_dns_client: placeholder
            :type  mock_dns_client: str
            :param mock_tm_client: placeholder
            :type  mock_tm_client: str

            :type return: AzureProvider
        '''
        provider = AzureProvider('mock_id', 'mock_client', 'mock_key',
                                 'mock_directory', 'mock_sub', 'mock_rg'
                                 )

        # Fetch the client to force it to load the creds
        provider._dns_client

        # set critical functions to return properly
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value = []
        tm_sync = provider._tm_client.profiles.create_or_update

        def side_effect(rg, name, profile):
            return Profile(
                id=profile.id,
                name=profile.name,
                traffic_routing_method=profile.traffic_routing_method,
                dns_config=profile.dns_config,
                monitor_config=profile.monitor_config,
                endpoints=profile.endpoints,
            )

        tm_sync.side_effect = side_effect

        return provider

    def _get_dynamic_record(self, zone):
        return Record.new(zone, 'foo', data={
            'type': 'CNAME',
            'ttl': 60,
            'value': 'default.unit.tests.',
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [
                            {'value': 'one.unit.tests.', 'weight': 1},
                        ],
                        'fallback': 'two',
                    },
                    'two': {
                        'values': [
                            {'value': 'two1.unit.tests.', 'weight': 3},
                            {'value': 'two2.unit.tests.', 'weight': 4},
                        ],
                        'fallback': 'three',
                    },
                    'three': {
                        'values': [
                            {'value': 'three.unit.tests.', 'weight': 1},
                        ],
                    },
                },
                'rules': [
                    {'geos': ['AF', 'EU-DE', 'NA-US-CA', 'OC'], 'pool': 'one'},
                    {'pool': 'two'},
                ],
            },
            'octodns': {
                'healthcheck': {
                    'path': '/_ping',
                    'port': 4443,
                    'protocol': 'HTTPS',
                }
            },
        })

    def _get_tm_profiles(self, provider):
        sub = provider._dns_client_subscription_id
        rg = provider._resource_group
        base_id = '/subscriptions/' + sub + \
            '/resourceGroups/' + rg + \
            '/providers/Microsoft.Network/trafficManagerProfiles/'
        prefix = 'foo--unit--tests'
        name_format = prefix + '-'
        id_format = base_id + name_format

        header = MonitorConfigCustomHeadersItem(name='Host',
                                                value='foo.unit.tests')
        monitor = MonitorConfig(protocol='HTTPS', port=4443, path='/_ping',
                                custom_headers=[header])
        external = 'Microsoft.Network/trafficManagerProfiles/externalEndpoints'
        nested = 'Microsoft.Network/trafficManagerProfiles/nestedEndpoints'

        profiles = [
            Profile(
                id=f'{id_format}pool-two',
                name=f'{name_format}pool-two',
                traffic_routing_method='Weighted',
                dns_config=DnsConfig(ttl=60),
                monitor_config=monitor,
                endpoints=[
                    Endpoint(
                        name='two--two1.unit.tests',
                        type=external,
                        target='two1.unit.tests',
                        weight=3,
                    ),
                    Endpoint(
                        name='two--two2.unit.tests',
                        type=external,
                        target='two2.unit.tests',
                        weight=4,
                    ),
                ],
            ),
            Profile(
                id=f'{id_format}rule-one',
                name=f'{name_format}rule-one',
                traffic_routing_method='Priority',
                dns_config=DnsConfig(ttl=60),
                monitor_config=monitor,
                endpoints=[
                    Endpoint(
                        name='one',
                        type=external,
                        target='one.unit.tests',
                        priority=1,
                    ),
                    Endpoint(
                        name='two',
                        type=nested,
                        target_resource_id=f'{id_format}pool-two',
                        priority=2,
                    ),
                    Endpoint(
                        name='three',
                        type=external,
                        target='three.unit.tests',
                        priority=3,
                    ),
                    Endpoint(
                        name='--default--',
                        type=external,
                        target='default.unit.tests',
                        priority=4,
                    ),
                ],
            ),
            Profile(
                id=f'{id_format}rule-two',
                name=f'{name_format}rule-two',
                traffic_routing_method='Priority',
                dns_config=DnsConfig(ttl=60),
                monitor_config=monitor,
                endpoints=[
                    Endpoint(
                        name='two',
                        type=nested,
                        target_resource_id=f'{id_format}pool-two',
                        priority=1,
                    ),
                    Endpoint(
                        name='three',
                        type=external,
                        target='three.unit.tests',
                        priority=2,
                    ),
                    Endpoint(
                        name='--default--',
                        type=external,
                        target='default.unit.tests',
                        priority=3,
                    ),
                ],
            ),
            Profile(
                id=base_id + prefix,
                name=prefix,
                traffic_routing_method='Geographic',
                dns_config=DnsConfig(ttl=60),
                monitor_config=monitor,
                endpoints=[
                    Endpoint(
                        geo_mapping=['GEO-AF', 'DE', 'US-CA', 'GEO-AP'],
                        name='one',
                        type=nested,
                        target_resource_id=f'{id_format}rule-one',
                    ),
                    Endpoint(
                        geo_mapping=['WORLD'],
                        name='two',
                        type=nested,
                        target_resource_id=f'{id_format}rule-two',
                    ),
                ],
            ),
        ]

        for profile in profiles:
            profile.dns_config.relative_name = profile.name

        return profiles

    def _get_dynamic_package(self):
        '''Convenience function to setup a sample dynamic record.
        '''
        provider = self._get_provider()

        # setup traffic manager profiles
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value = self._get_tm_profiles(provider)

        # setup zone with dynamic record
        zone = Zone(name='unit.tests.', sub_zones=[])
        record = self._get_dynamic_record(zone)
        zone.add_record(record)

        # return everything
        return provider, zone, record

    def test_populate_records(self):
        provider = self._get_provider()

        rs = []
        recordSet = RecordSet(a_records=[ARecord(ipv4_address='1.1.1.1')])
        recordSet.name, recordSet.ttl, recordSet.type = 'a1', 0, 'A'
        recordSet.target_resource = SubResource()
        rs.append(recordSet)
        recordSet = RecordSet(a_records=[ARecord(ipv4_address='1.1.1.1'),
                                         ARecord(ipv4_address='2.2.2.2')])
        recordSet.name, recordSet.ttl, recordSet.type = 'a2', 1, 'A'
        recordSet.target_resource = SubResource()
        rs.append(recordSet)
        aaaa1 = AaaaRecord(ipv6_address='1:1ec:1::1')
        recordSet = RecordSet(aaaa_records=[aaaa1])
        recordSet.name, recordSet.ttl, recordSet.type = 'aaaa1', 2, 'AAAA'
        recordSet.target_resource = SubResource()
        rs.append(recordSet)
        aaaa2 = AaaaRecord(ipv6_address='1:1ec:1::2')
        recordSet = RecordSet(aaaa_records=[aaaa1,
                                            aaaa2])
        recordSet.name, recordSet.ttl, recordSet.type = 'aaaa2', 3, 'AAAA'
        recordSet.target_resource = SubResource()
        rs.append(recordSet)
        recordSet = RecordSet(caa_records=[CaaRecord(flags=0,
                                                     tag='issue',
                                                     value='caa1.unit.tests')])
        recordSet.name, recordSet.ttl, recordSet.type = 'caa1', 4, 'CAA'
        rs.append(recordSet)
        recordSet = RecordSet(caa_records=[CaaRecord(flags=0,
                                                     tag='issue',
                                                     value='caa1.unit.tests'),
                                           CaaRecord(flags=0,
                                                     tag='issue',
                                                     value='caa2.unit.tests')])
        recordSet.name, recordSet.ttl, recordSet.type = 'caa2', 4, 'CAA'
        rs.append(recordSet)
        cname1 = CnameRecord(cname='cname.unit.test.')
        recordSet = RecordSet(cname_record=cname1)
        recordSet.name, recordSet.ttl, recordSet.type = 'cname1', 5, 'CNAME'
        recordSet.target_resource = SubResource()
        rs.append(recordSet)
        recordSet = RecordSet(mx_records=[MxRecord(preference=10,
                                                   exchange='mx1.unit.test.')])
        recordSet.name, recordSet.ttl, recordSet.type = 'mx1', 7, 'MX'
        rs.append(recordSet)
        recordSet = RecordSet(mx_records=[MxRecord(preference=10,
                                                   exchange='mx1.unit.test.'),
                                          MxRecord(preference=11,
                                                   exchange='mx2.unit.test.')])
        recordSet.name, recordSet.ttl, recordSet.type = 'mx2', 8, 'MX'
        rs.append(recordSet)
        recordSet = RecordSet(ns_records=[NsRecord(nsdname='ns1.unit.test.')])
        recordSet.name, recordSet.ttl, recordSet.type = 'ns1', 9, 'NS'
        rs.append(recordSet)
        recordSet = RecordSet(ns_records=[NsRecord(nsdname='ns1.unit.test.'),
                                          NsRecord(nsdname='ns2.unit.test.')])
        recordSet.name, recordSet.ttl, recordSet.type = 'ns2', 10, 'NS'
        rs.append(recordSet)
        ptr1 = PtrRecord(ptrdname='ptr1.unit.test.')
        recordSet = RecordSet(ptr_records=[ptr1])
        recordSet.name, recordSet.ttl, recordSet.type = 'ptr1', 11, 'PTR'
        rs.append(recordSet)
        recordSet = RecordSet(srv_records=[SrvRecord(priority=1,
                                                     weight=2,
                                                     port=3,
                                                     target='1unit.tests.')])
        recordSet.name, recordSet.ttl, recordSet.type = '_srv1._tcp', 13, 'SRV'
        rs.append(recordSet)
        recordSet = RecordSet(srv_records=[SrvRecord(priority=1,
                                                     weight=2,
                                                     port=3,
                                                     target='1unit.tests.'),
                                           SrvRecord(priority=4,
                                                     weight=5,
                                                     port=6,
                                                     target='2unit.tests.')])
        recordSet.name, recordSet.ttl, recordSet.type = '_srv2._tcp', 14, 'SRV'
        rs.append(recordSet)
        recordSet = RecordSet(txt_records=[TxtRecord(value='sample text1')])
        recordSet.name, recordSet.ttl, recordSet.type = 'txt1', 15, 'TXT'
        recordSet.target_resource = SubResource()
        rs.append(recordSet)
        recordSet = RecordSet(txt_records=[TxtRecord(value='sample text1'),
                                           TxtRecord(value='sample text2')])
        recordSet.name, recordSet.ttl, recordSet.type = 'txt2', 16, 'TXT'
        recordSet.target_resource = SubResource()
        rs.append(recordSet)
        recordSet = RecordSet(soa_record=[SoaRecord()])
        recordSet.name, recordSet.ttl, recordSet.type = '', 17, 'SOA'
        rs.append(recordSet)
        long_txt = "v=spf1 ip4:10.10.0.0/24 ip4:10.10.1.0/24 ip4:10.10.2.0/24"
        long_txt += " ip4:10.10.3.0/24 ip4:10.10.4.0/24 ip4:10.10.5.0/24 "
        long_txt += " 10.6.0/24 ip4:10.10.7.0/24 ip4:10.10.8.0/24 "
        long_txt += " ip4:10.10.10.0/24 ip4:10.10.11.0/24 ip4:10.10.12.0/24"
        long_txt += " ip4:10.10.13.0/24 ip4:10.10.14.0/24 ip4:10.10.15.0/24"
        long_txt += " ip4:10.10.16.0/24 ip4:10.10.17.0/24 ip4:10.10.18.0/24"
        long_txt += " ip4:10.10.19.0/24 ip4:10.10.20.0/24  ~all"
        recordSet = RecordSet(txt_records=[TxtRecord(value='sample value1'),
                                           TxtRecord(value=long_txt)])
        recordSet.name, recordSet.ttl, recordSet.type = 'txt3', 18, 'TXT'
        recordSet.target_resource = SubResource()
        rs.append(recordSet)

        record_list = provider._dns_client.record_sets.list_by_dns_zone
        record_list.return_value = rs

        zone_list = provider._dns_client.zones.list_by_resource_group
        zone_list.return_value = [zone]

        exists = provider.populate(zone)

        self.assertEquals(len(zone.records), 17)
        self.assertTrue(exists)

    def test_populate_zone(self):
        provider = self._get_provider()

        zone_list = provider._dns_client.zones.list_by_resource_group
        zone_1 = AzureZone(location='global')
        # This is far from ideal but the
        # zone constructor doesn't let me set it on creation
        zone_1.name = "zone-1"
        zone_2 = AzureZone(location='global')
        # This is far from ideal but the
        # zone constructor doesn't let me set it on creation
        zone_2.name = "zone-2"
        zone_list.return_value = [zone_1,
                                  zone_2,
                                  zone_1]

        provider._populate_zones()

        # This should be returning two zones since two zones are the same
        self.assertEquals(len(provider._azure_zones), 2)

    def test_bad_zone_response(self):
        provider = self._get_provider()

        _get = provider._dns_client.zones.get
        _get.side_effect = CloudError(Mock(status=404), 'Azure Error')
        self.assertEquals(
            provider._check_zone('unit.test', create=False),
            None
        )

    def test_extra_changes(self):
        provider, existing, record = self._get_dynamic_package()

        # test simple records produce no extra changes
        desired = Zone(name=existing.name, sub_zones=[])
        simple = Record.new(desired, 'simple', data={
            'type': record._type,
            'ttl': record.ttl,
            'value': record.value,
        })
        desired.add_record(simple)
        extra = provider._extra_changes(desired, desired, [Create(simple)])
        self.assertEqual(len(extra), 0)

        # test an unchanged dynamic record produces no extra changes
        desired.add_record(record)
        extra = provider._extra_changes(existing, desired, [])
        self.assertEqual(len(extra), 0)

        # test unused TM produces the extra change for clean up
        sample_profile = self._get_tm_profiles(provider)[0]
        tm_id = provider._profile_name_to_id
        root_profile_name = _root_traffic_manager_name(record)
        extra_profile = Profile(
            id=tm_id(f'{root_profile_name}-pool-random'),
            name=f'{root_profile_name}-pool-random',
            traffic_routing_method='Weighted',
            dns_config=sample_profile.dns_config,
            monitor_config=sample_profile.monitor_config,
            endpoints=sample_profile.endpoints,
        )
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value.append(extra_profile)
        provider._populate_traffic_managers()
        extra = provider._extra_changes(existing, desired, [])
        self.assertEqual(len(extra), 1)
        extra = extra[0]
        self.assertIsInstance(extra, Update)
        self.assertEqual(extra.new, record)
        desired._remove_record(record)
        tm_list.return_value.pop()

        # test new dynamic record does not produce an extra change for it
        new_dynamic = Record.new(desired, record.name + '2', data={
            'type': record._type,
            'ttl': record.ttl,
            'value': record.value,
            'dynamic': record.dynamic._data(),
            'octodns': record._octodns,
        })
        # test change in healthcheck by using a different port number
        update_dynamic = Record.new(desired, record.name, data={
            'type': record._type,
            'ttl': record.ttl,
            'value': record.value,
            'dynamic': record.dynamic._data(),
            'octodns': {
                'healthcheck': {
                    'path': '/_ping',
                    'port': 443,
                    'protocol': 'HTTPS',
                },
            },
        })
        desired.add_record(new_dynamic)
        desired.add_record(update_dynamic)
        changes = [Create(new_dynamic)]
        extra = provider._extra_changes(existing, desired, changes)
        # implicitly asserts that new_dynamic was not added to extra changes
        # as it was already in the `changes` list
        self.assertEqual(len(extra), 1)
        extra = extra[0]
        self.assertIsInstance(extra, Update)
        self.assertEqual(extra.new, update_dynamic)

        # test dynamic record of unsupported type throws exception
        unsupported_dynamic = Record.new(desired, record.name + '3', data={
            'type': 'DNAME',
            'ttl': record.ttl,
            'value': 'default.unit.tests.',
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': 'one.unit.tests.'}]},
                },
                'rules': [
                    {'pool': 'one'},
                ],
            },
        })
        desired.add_record(unsupported_dynamic)
        changes = [Create(unsupported_dynamic)]
        with self.assertRaises(AzureException) as ctx:
            provider._extra_changes(existing, desired, changes)
            self.assertTrue(str(ctx).endswith('must be of type CNAME'))
        desired._remove_record(unsupported_dynamic)

        # test colliding ATM names throws exception
        record1 = Record.new(desired, 'sub.www', data={
            'type': record._type,
            'ttl': record.ttl,
            'value': record.value,
            'dynamic': record.dynamic._data(),
        })
        record2 = Record.new(desired, 'sub--www', data={
            'type': record._type,
            'ttl': record.ttl,
            'value': record.value,
            'dynamic': record.dynamic._data(),
        })
        desired.add_record(record1)
        desired.add_record(record2)
        changes = [Create(record1), Create(record2)]
        with self.assertRaises(AzureException) as ctx:
            provider._extra_changes(existing, desired, changes)
            self.assertTrue(str(ctx)
                            .startswith('Collision in Traffic Manager'))

    @patch(
        'octodns.provider.azuredns.AzureProvider._generate_traffic_managers')
    def test_extra_changes_non_last_fallback_contains_default(self, mock_gtm):
        provider = self._get_provider()

        desired = Zone(zone.name, sub_zones=[])
        record = Record.new(desired, 'foo', {
            'type': 'CNAME',
            'ttl': 60,
            'value': 'default.unit.tests.',
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{'value': 'one.unit.tests.'}],
                        'fallback': 'def',
                    },
                    'def': {
                        'values': [{'value': 'default.unit.tests.'}],
                        'fallback': 'two',
                    },
                    'two': {
                        'values': [{'value': 'two.unit.tests.'}],
                    },
                },
                'rules': [
                    {'pool': 'one'},
                ]
            }
        })
        desired.add_record(record)
        changes = [Create(record)]

        # assert that no exception is raised
        provider._extra_changes(zone, desired, changes)

        # simulate duplicate endpoint and assert exception
        endpoint = Endpoint(target='dup.unit.tests.')
        mock_gtm.return_value = [Profile(
            name='test-profile',
            endpoints=[endpoint, endpoint],
        )]
        with self.assertRaises(AzureException) as ctx:
            provider._extra_changes(zone, desired, changes)
            self.assertTrue('duplicate endpoint' in str(ctx))

    def test_extra_changes_A_multi_defaults(self):
        provider = self._get_provider()

        record = Record.new(zone, 'foo', data={
            'type': 'A',
            'ttl': 60,
            'values': ['1.1.1.1', '8.8.8.8'],
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{'value': '1.1.1.1'}],
                    },
                },
                'rules': [
                    {'pool': 'one'},
                ],
            }
        })

        # test that extra changes doesn't show any changes
        desired = Zone(zone.name, sub_zones=[])
        desired.add_record(record)
        with self.assertRaises(AzureException) as ctx:
            provider._extra_changes(zone, desired, [])
            self.assertEqual('single value' in str(ctx))

    def test_generate_tm_profile(self):
        provider, zone, record = self._get_dynamic_package()
        profile_gen = provider._generate_tm_profile

        label = 'foobar'
        routing = 'Priority'
        endpoints = [
            Endpoint(target='one.unit.tests'),
            Endpoint(target_resource_id='/s/1/rg/foo/tm/foobar2'),
            Endpoint(name='invalid'),
        ]

        # invalid endpoint raises exception
        with self.assertRaises(AzureException):
            profile_gen(routing, endpoints, record, label)

        # regular test
        endpoints.pop()
        profile = profile_gen(routing, endpoints, record, label)

        # implicitly tests _profile_name_to_id
        sub = provider._dns_client_subscription_id
        rg = provider._resource_group
        expected_name = 'foo--unit--tests-rule-foobar'
        expected_id = '/subscriptions/' + sub + \
            '/resourceGroups/' + rg + \
            '/providers/Microsoft.Network/trafficManagerProfiles/' + \
            expected_name
        self.assertEqual(profile.id, expected_id)
        self.assertEqual(profile.name, expected_name)
        self.assertEqual(profile.name, profile.dns_config.relative_name)
        self.assertEqual(profile.traffic_routing_method, routing)
        self.assertEqual(profile.dns_config.ttl, record.ttl)
        self.assertEqual(len(profile.endpoints), len(endpoints))

        self.assertEqual(
            profile.endpoints[0].type,
            'Microsoft.Network/trafficManagerProfiles/externalEndpoints'
        )
        self.assertEqual(
            profile.endpoints[1].type,
            'Microsoft.Network/trafficManagerProfiles/nestedEndpoints'
        )

    def test_dynamic_record(self):
        provider, zone, record = self._get_dynamic_package()
        profiles = provider._generate_traffic_managers(record)

        # check that every profile is a match with what we expect
        expected_profiles = self._get_tm_profiles(provider)
        self.assertEqual(len(expected_profiles), len(profiles))
        for have, expected in zip(profiles, expected_profiles):
            self.assertTrue(_profile_is_match(have, expected))

        # check that dynamic record is populated back from profiles
        azrecord = RecordSet(
            ttl=60,
            target_resource=SubResource(id=profiles[-1].id),
        )
        azrecord.name = record.name or '@'
        azrecord.type = f'Microsoft.Network/dnszones/{record._type}'
        record2 = provider._populate_record(zone, azrecord)
        self.assertEqual(record2.dynamic._data(), record.dynamic._data())

        # test that extra changes doesn't show any changes
        desired = Zone(zone.name, sub_zones=[])
        desired.add_record(record)
        changes = provider._extra_changes(zone, desired, [])
        self.assertEqual(len(changes), 0)

    def test_generate_traffic_managers_middle_east(self):
        # check Asia/Middle East test case
        provider, zone, record = self._get_dynamic_package()
        record.dynamic._data()['rules'][0]['geos'].append('AS')
        profiles = provider._generate_traffic_managers(record)
        self.assertIn('GEO-ME', profiles[-1].endpoints[0].geo_mapping)
        self.assertIn('GEO-AS', profiles[-1].endpoints[0].geo_mapping)

    def test_populate_dynamic_middle_east(self):
        # Middle east without Asia raises exception
        provider, zone, record = self._get_dynamic_package()
        tm_suffix = _root_traffic_manager_name(record)
        tm_id = provider._profile_name_to_id
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value = [
            Profile(
                id=tm_id(tm_suffix),
                name=tm_suffix,
                traffic_routing_method='Geographic',
                endpoints=[
                    Endpoint(
                        geo_mapping=['GEO-ME'],
                    ),
                ],
            ),
        ]
        azrecord = RecordSet(
            ttl=60,
            target_resource=SubResource(id=tm_id(tm_suffix)),
        )
        azrecord.name = record.name or '@'
        azrecord.type = f'Microsoft.Network/dnszones/{record._type}'
        with self.assertRaises(AzureException) as ctx:
            provider._populate_record(zone, azrecord)
            self.assertTrue(str(ctx).startswith(
                'Middle East (GEO-ME) is not supported'
            ))

        # valid profiles with Middle East test case
        provider, zone, record = self._get_dynamic_package()
        geo_profile = provider._get_tm_for_dynamic_record(record)
        geo_profile.endpoints[0].geo_mapping.extend(['GEO-ME', 'GEO-AS'])
        record = provider._populate_record(zone, azrecord)
        self.assertIn('AS', record.dynamic.rules[0].data['geos'])
        self.assertNotIn('ME', record.dynamic.rules[0].data['geos'])

    def test_dynamic_no_geo(self):
        # test that traffic managers are generated as expected
        provider = self._get_provider()
        external = 'Microsoft.Network/trafficManagerProfiles/externalEndpoints'

        record = Record.new(zone, 'foo', data={
            'type': 'CNAME',
            'ttl': 60,
            'value': 'default.unit.tests.',
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [
                            {'value': 'one.unit.tests.'},
                        ],
                    },
                },
                'rules': [
                    {'pool': 'one'},
                ],
            }
        })
        profiles = provider._generate_traffic_managers(record)

        self.assertEqual(len(profiles), 1)
        self.assertTrue(_profile_is_match(profiles[0], Profile(
            name='foo--unit--tests',
            traffic_routing_method='Priority',
            dns_config=DnsConfig(
                relative_name='foo--unit--tests', ttl=60),
            monitor_config=_get_monitor(record),
            endpoints=[
                Endpoint(
                    name='one',
                    type=external,
                    target='one.unit.tests',
                    priority=1,
                ),
                Endpoint(
                    name='--default--',
                    type=external,
                    target='default.unit.tests',
                    priority=2,
                ),
            ],
        )))

        # test that same record gets populated back from traffic managers
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value = profiles
        azrecord = RecordSet(
            ttl=60,
            target_resource=SubResource(id=profiles[-1].id),
        )
        azrecord.name = record.name or '@'
        azrecord.type = f'Microsoft.Network/dnszones/{record._type}'
        record2 = provider._populate_record(zone, azrecord)
        self.assertEqual(record2.dynamic._data(), record.dynamic._data())

        # test that extra changes doesn't show any changes
        desired = Zone(zone.name, sub_zones=[])
        desired.add_record(record)
        changes = provider._extra_changes(zone, desired, [])
        self.assertEqual(len(changes), 0)

    def test_dynamic_fallback_is_default(self):
        # test that traffic managers are generated as expected
        provider = self._get_provider()
        external = 'Microsoft.Network/trafficManagerProfiles/externalEndpoints'

        record = Record.new(zone, 'foo', data={
            'type': 'CNAME',
            'ttl': 60,
            'value': 'default.unit.tests.',
            'dynamic': {
                'pools': {
                    'def': {
                        'values': [
                            {'value': 'default.unit.tests.'},
                        ],
                    },
                },
                'rules': [
                    {'geos': ['AF'], 'pool': 'def'},
                ],
            }
        })
        profiles = provider._generate_traffic_managers(record)

        self.assertEqual(len(profiles), 1)
        self.assertTrue(_profile_is_match(profiles[0], Profile(
            name='foo--unit--tests',
            traffic_routing_method='Geographic',
            dns_config=DnsConfig(
                relative_name='foo--unit--tests', ttl=60),
            monitor_config=_get_monitor(record),
            endpoints=[
                Endpoint(
                    name='def--default--',
                    type=external,
                    target='default.unit.tests',
                    geo_mapping=['GEO-AF'],
                ),
            ],
        )))

        # test that same record gets populated back from traffic managers
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value = profiles
        azrecord = RecordSet(
            ttl=60,
            target_resource=SubResource(id=profiles[-1].id),
        )
        azrecord.name = record.name or '@'
        azrecord.type = f'Microsoft.Network/dnszones/{record._type}'
        record2 = provider._populate_record(zone, azrecord)
        self.assertEqual(record2.dynamic._data(), record.dynamic._data())

        # test that extra changes doesn't show any changes
        desired = Zone(zone.name, sub_zones=[])
        desired.add_record(record)
        changes = provider._extra_changes(zone, desired, [])
        self.assertEqual(len(changes), 0)

    def test_dynamic_pool_contains_default(self):
        # test that traffic managers are generated as expected
        provider = self._get_provider()
        external = 'Microsoft.Network/trafficManagerProfiles/externalEndpoints'
        nested = 'Microsoft.Network/trafficManagerProfiles/nestedEndpoints'

        record = Record.new(zone, 'foo', data={
            'type': 'CNAME',
            'ttl': 60,
            'value': 'default.unit.tests.',
            'dynamic': {
                'pools': {
                    'rr': {
                        'values': [
                            {'value': 'one.unit.tests.'},
                            {'value': 'two.unit.tests.'},
                            {'value': 'default.unit.tests.'},
                            {'value': 'final.unit.tests.'},
                        ],
                    },
                },
                'rules': [
                    {'geos': ['AF'], 'pool': 'rr'},
                ],
            }
        })
        profiles = provider._generate_traffic_managers(record)

        self.assertEqual(len(profiles), 2)
        self.assertTrue(_profile_is_match(profiles[0], Profile(
            name='foo--unit--tests-pool-rr',
            traffic_routing_method='Weighted',
            dns_config=DnsConfig(
                relative_name='foo--unit--tests-pool-rr', ttl=60),
            monitor_config=_get_monitor(record),
            endpoints=[
                Endpoint(
                    name='rr--one.unit.tests',
                    type=external,
                    target='one.unit.tests',
                    weight=1,
                ),
                Endpoint(
                    name='rr--two.unit.tests',
                    type=external,
                    target='two.unit.tests',
                    weight=1,
                ),
                Endpoint(
                    name='rr--default.unit.tests--default--',
                    type=external,
                    target='default.unit.tests',
                    weight=1,
                ),
                Endpoint(
                    name='rr--final.unit.tests',
                    type=external,
                    target='final.unit.tests',
                    weight=1,
                ),
            ],
        )))
        self.assertTrue(_profile_is_match(profiles[1], Profile(
            name='foo--unit--tests',
            traffic_routing_method='Geographic',
            dns_config=DnsConfig(
                relative_name='foo--unit--tests', ttl=60),
            monitor_config=_get_monitor(record),
            endpoints=[
                Endpoint(
                    name='rr',
                    type=nested,
                    target_resource_id=profiles[0].id,
                    geo_mapping=['GEO-AF'],
                ),
            ],
        )))

        # test that same record gets populated back from traffic managers
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value = profiles
        azrecord = RecordSet(
            ttl=60,
            target_resource=SubResource(id=profiles[-1].id),
        )
        azrecord.name = record.name or '@'
        azrecord.type = f'Microsoft.Network/dnszones/{record._type}'
        record2 = provider._populate_record(zone, azrecord)
        self.assertEqual(record2.dynamic._data(), record.dynamic._data())

        # test that extra changes doesn't show any changes
        desired = Zone(zone.name, sub_zones=[])
        desired.add_record(record)
        changes = provider._extra_changes(zone, desired, [])
        self.assertEqual(len(changes), 0)

    def test_dynamic_pool_contains_default_no_geo(self):
        # test that traffic managers are generated as expected
        provider = self._get_provider()
        external = 'Microsoft.Network/trafficManagerProfiles/externalEndpoints'

        record = Record.new(zone, 'foo', data={
            'type': 'CNAME',
            'ttl': 60,
            'value': 'default.unit.tests.',
            'dynamic': {
                'pools': {
                    'rr': {
                        'values': [
                            {'value': 'one.unit.tests.'},
                            {'value': 'two.unit.tests.'},
                            {'value': 'default.unit.tests.'},
                            {'value': 'final.unit.tests.'},
                        ],
                    },
                },
                'rules': [
                    {'pool': 'rr'},
                ],
            }
        })
        profiles = provider._generate_traffic_managers(record)

        self.assertEqual(len(profiles), 1)
        self.assertTrue(_profile_is_match(profiles[0], Profile(
            name='foo--unit--tests',
            traffic_routing_method='Weighted',
            dns_config=DnsConfig(
                relative_name='foo--unit--tests', ttl=60),
            monitor_config=_get_monitor(record),
            endpoints=[
                Endpoint(
                    name='rr--one.unit.tests',
                    type=external,
                    target='one.unit.tests',
                    weight=1,
                ),
                Endpoint(
                    name='rr--two.unit.tests',
                    type=external,
                    target='two.unit.tests',
                    weight=1,
                ),
                Endpoint(
                    name='rr--default.unit.tests--default--',
                    type=external,
                    target='default.unit.tests',
                    weight=1,
                ),
                Endpoint(
                    name='rr--final.unit.tests',
                    type=external,
                    target='final.unit.tests',
                    weight=1,
                ),
            ],
        )))

        # test that same record gets populated back from traffic managers
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value = profiles
        azrecord = RecordSet(
            ttl=60,
            target_resource=SubResource(id=profiles[-1].id),
        )
        azrecord.name = record.name or '@'
        azrecord.type = f'Microsoft.Network/dnszones/{record._type}'
        record2 = provider._populate_record(zone, azrecord)
        self.assertEqual(record2.dynamic._data(), record.dynamic._data())

        # test that extra changes doesn't show any changes
        desired = Zone(zone.name, sub_zones=[])
        desired.add_record(record)
        changes = provider._extra_changes(zone, desired, [])
        self.assertEqual(len(changes), 0)

    def test_dynamic_last_pool_contains_default_no_geo(self):
        # test that traffic managers are generated as expected
        provider = self._get_provider()
        external = 'Microsoft.Network/trafficManagerProfiles/externalEndpoints'
        nested = 'Microsoft.Network/trafficManagerProfiles/nestedEndpoints'

        record = Record.new(zone, 'foo', data={
            'type': 'CNAME',
            'ttl': 60,
            'value': 'default.unit.tests.',
            'dynamic': {
                'pools': {
                    'cloud': {
                        'values': [
                            {'value': 'cloud.unit.tests.'},
                        ],
                        'fallback': 'rr',
                    },
                    'rr': {
                        'values': [
                            {'value': 'one.unit.tests.'},
                            {'value': 'two.unit.tests.'},
                            {'value': 'default.unit.tests.'},
                            {'value': 'final.unit.tests.'},
                        ],
                    },
                },
                'rules': [
                    {'pool': 'cloud'},
                ],
            }
        })
        profiles = provider._generate_traffic_managers(record)

        self.assertEqual(len(profiles), 2)
        self.assertTrue(_profile_is_match(profiles[0], Profile(
            name='foo--unit--tests-pool-rr',
            traffic_routing_method='Weighted',
            dns_config=DnsConfig(
                relative_name='foo--unit--tests-pool-rr', ttl=60),
            monitor_config=_get_monitor(record),
            endpoints=[
                Endpoint(
                    name='rr--one.unit.tests',
                    type=external,
                    target='one.unit.tests',
                    weight=1,
                ),
                Endpoint(
                    name='rr--two.unit.tests',
                    type=external,
                    target='two.unit.tests',
                    weight=1,
                ),
                Endpoint(
                    name='rr--default.unit.tests--default--',
                    type=external,
                    target='default.unit.tests',
                    weight=1,
                ),
                Endpoint(
                    name='rr--final.unit.tests',
                    type=external,
                    target='final.unit.tests',
                    weight=1,
                ),
            ],
        )))
        self.assertTrue(_profile_is_match(profiles[1], Profile(
            name='foo--unit--tests',
            traffic_routing_method='Priority',
            dns_config=DnsConfig(
                relative_name='foo--unit--tests', ttl=60),
            monitor_config=_get_monitor(record),
            endpoints=[
                Endpoint(
                    name='cloud',
                    type=external,
                    target='cloud.unit.tests',
                    priority=1,
                ),
                Endpoint(
                    name='rr',
                    type=nested,
                    target_resource_id=profiles[0].id,
                    priority=2,
                ),
            ],
        )))

        # test that same record gets populated back from traffic managers
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value = profiles
        azrecord = RecordSet(
            ttl=60,
            target_resource=SubResource(id=profiles[-1].id),
        )
        azrecord.name = record.name or '@'
        azrecord.type = f'Microsoft.Network/dnszones/{record._type}'
        record2 = provider._populate_record(zone, azrecord)
        self.assertEqual(record2.dynamic._data(), record.dynamic._data())

        # test that extra changes doesn't show any changes
        desired = Zone(zone.name, sub_zones=[])
        desired.add_record(record)
        changes = provider._extra_changes(zone, desired, [])
        self.assertEqual(len(changes), 0)

    def test_dynamic_unique_traffic_managers(self):
        record = self._get_dynamic_record(zone)
        data = {
            'type': record._type,
            'ttl': record.ttl,
            'value': record.value,
            'dynamic': record.dynamic._data()
        }
        record_names = [
            'www.foo', 'www-foo'
        ]
        provider = self._get_provider()

        seen = set()
        for name in record_names:
            record = Record.new(zone, name, data=data)
            tms = provider._generate_traffic_managers(record)
            for tm in tms:
                self.assertNotIn(tm.name, seen)
                seen.add(tm.name)

    def test_dynamic_reused_pool(self):
        # test that traffic managers are generated as expected
        provider = self._get_provider()
        nested = 'Microsoft.Network/trafficManagerProfiles/nestedEndpoints'

        record = Record.new(zone, 'foo', data={
            'type': 'CNAME',
            'ttl': 60,
            'value': 'default.unit.tests.',
            'dynamic': {
                'pools': {
                    'sto': {
                        'values': [
                            {'value': 'sto.unit.tests.'},
                        ],
                        'fallback': 'iad',
                    },
                    'iad': {
                        'values': [
                            {'value': 'iad.unit.tests.'},
                        ],
                        'fallback': 'lhr',
                    },
                    'lhr': {
                        'values': [
                            {'value': 'lhr.unit.tests.'},
                        ],
                    },
                },
                'rules': [
                    {'geos': ['EU'], 'pool': 'iad'},
                    {'geos': ['EU-GB'], 'pool': 'lhr'},
                    {'geos': ['EU-SE'], 'pool': 'sto'},
                    {'pool': 'lhr'},
                ],
            }
        })
        profiles = provider._generate_traffic_managers(record)

        self.assertEqual(len(profiles), 4)
        self.assertTrue(_profile_is_match(profiles[-1], Profile(
            name='foo--unit--tests',
            traffic_routing_method='Geographic',
            dns_config=DnsConfig(
                relative_name='foo--unit--tests', ttl=record.ttl),
            monitor_config=_get_monitor(record),
            endpoints=[
                Endpoint(
                    name='iad',
                    type=nested,
                    target_resource_id=profiles[0].id,
                    geo_mapping=['GEO-EU'],
                ),
                Endpoint(
                    name='lhr',
                    type=nested,
                    target_resource_id=profiles[1].id,
                    geo_mapping=['GB', 'WORLD'],
                ),
                Endpoint(
                    name='sto',
                    type=nested,
                    target_resource_id=profiles[2].id,
                    geo_mapping=['SE'],
                ),
            ],
        )))

        # test that same record gets populated back from traffic managers
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value = profiles
        azrecord = RecordSet(
            ttl=60,
            target_resource=SubResource(id=profiles[-1].id),
        )
        azrecord.name = record.name or '@'
        azrecord.type = f'Microsoft.Network/dnszones/{record._type}'
        record2 = provider._populate_record(zone, azrecord)
        self.assertEqual(record2.dynamic._data(), record.dynamic._data())

        # test that extra changes doesn't show any changes
        desired = Zone(zone.name, sub_zones=[])
        desired.add_record(record)
        changes = provider._extra_changes(zone, desired, [])
        self.assertEqual(len(changes), 0)

    def test_dynamic_pool_status(self):
        # test that traffic managers are generated as expected for pool value
        # statuses
        provider = self._get_provider()
        zone1 = Zone('unit.tests.', [])
        record1 = Record.new(zone1, 'foo', data={
            'type': 'CNAME',
            'ttl': 60,
            'value': 'default.unit.tests.',
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [
                            {'value': 'one1.unit.tests.', 'status': 'up'},
                        ],
                    },
                    'two': {
                        'values': [
                            {'value': 'two1.unit.tests.', 'status': 'down'},
                            {'value': 'two2.unit.tests.'},
                        ],
                    },
                },
                'rules': [
                    {'geos': ['AS'], 'pool': 'one'},
                    {'pool': 'two'},
                ],
            }
        })
        zone1.add_record(record1)
        zone2 = provider._process_desired_zone(zone1.copy())
        record2 = list(zone2.records)[0]
        self.assertTrue(
            record2.dynamic.pools['one'].data['values'][0]['status'],
            'obey'
        )

        record1.dynamic.pools['one'].data['values'][0]['status'] = 'down'
        profiles = provider._generate_traffic_managers(record1)
        self.assertEqual(len(profiles), 4)
        self.assertEqual(profiles[0].endpoints[0].endpoint_status, 'Disabled')
        self.assertEqual(profiles[1].endpoints[0].endpoint_status, 'Disabled')

        # test that same record gets populated back from traffic managers
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value = profiles
        azrecord = RecordSet(
            ttl=60,
            target_resource=SubResource(id=profiles[-1].id),
        )
        azrecord.name = record1.name or '@'
        azrecord.type = f'Microsoft.Network/dnszones/{record1._type}'
        record2 = provider._populate_record(zone, azrecord)
        self.assertEqual(record1.dynamic._data(), record2.dynamic._data())

        # _process_desired_zone shouldn't change anything when status value is
        # supported
        zone1 = Zone(zone.name, sub_zones=[])
        zone1.add_record(record1)
        zone2 = provider._process_desired_zone(zone1.copy())
        record2 = list(zone2.records)[0]
        self.assertTrue(record1.data, record2.data)

        # simple records should not get changed by _process_desired_zone
        zone1 = Zone(zone.name, sub_zones=[])
        record1 = Record.new(zone1, 'foo', data={
            'type': 'CNAME',
            'ttl': 86400,
            'value': 'one.unit.tests.',
        })
        zone1.add_record(record1)
        zone2 = provider._process_desired_zone(zone1.copy())
        record2 = list(zone2.records)[0]
        self.assertTrue(record1.data, record2.data)

    def test_dynamic_A(self):
        provider = self._get_provider()
        external = 'Microsoft.Network/trafficManagerProfiles/externalEndpoints'
        nested = 'Microsoft.Network/trafficManagerProfiles/nestedEndpoints'

        record = Record.new(zone, 'foo', data={
            'type': 'A',
            'ttl': 60,
            'values': ['9.9.9.9'],
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [
                            {'value': '11.11.11.11'},
                            {'value': '12.12.12.12'},
                        ],
                        'fallback': 'two'
                    },
                    'two': {
                        'values': [
                            {'value': '2.2.2.2'},
                        ],
                    },
                },
                'rules': [
                    {'geos': ['AF'], 'pool': 'one'},
                    {'pool': 'two'},
                ],
            }
        })

        profiles = provider._generate_traffic_managers(record)

        self.assertEqual(len(profiles), 4)
        self.assertTrue(_profile_is_match(profiles[0], Profile(
            name='foo--unit--tests-A-pool-one',
            traffic_routing_method='Weighted',
            dns_config=DnsConfig(
                relative_name='foo--unit--tests-a-pool-one', ttl=record.ttl),
            monitor_config=_get_monitor(record),
            endpoints=[
                Endpoint(
                    name='one--11.11.11.11',
                    type=external,
                    target='11.11.11.11',
                    weight=1,
                ),
                Endpoint(
                    name='one--12.12.12.12',
                    type=external,
                    target='12.12.12.12',
                    weight=1,
                ),
            ],
        )))
        self.assertTrue(_profile_is_match(profiles[1], Profile(
            name='foo--unit--tests-A-rule-one',
            traffic_routing_method='Priority',
            dns_config=DnsConfig(
                relative_name='foo--unit--tests-a-rule-one', ttl=record.ttl),
            monitor_config=_get_monitor(record),
            endpoints=[
                Endpoint(
                    name='one',
                    type=nested,
                    target_resource_id=profiles[0].id,
                    priority=1,
                ),
                Endpoint(
                    name='two',
                    type=external,
                    target='2.2.2.2',
                    priority=2,
                ),
                Endpoint(
                    name='--default--',
                    type=external,
                    target='9.9.9.9',
                    priority=3,
                ),
            ],
        )))
        self.assertTrue(_profile_is_match(profiles[2], Profile(
            name='foo--unit--tests-A-rule-two',
            traffic_routing_method='Priority',
            dns_config=DnsConfig(
                relative_name='foo--unit--tests-a-rule-two', ttl=record.ttl),
            monitor_config=_get_monitor(record),
            endpoints=[
                Endpoint(
                    name='two',
                    type=external,
                    target='2.2.2.2',
                    priority=1,
                ),
                Endpoint(
                    name='--default--',
                    type=external,
                    target='9.9.9.9',
                    priority=2,
                ),
            ],
        )))
        self.assertTrue(_profile_is_match(profiles[3], Profile(
            name='foo--unit--tests-A',
            traffic_routing_method='Geographic',
            dns_config=DnsConfig(
                relative_name='foo--unit--tests-a', ttl=record.ttl),
            monitor_config=_get_monitor(record),
            endpoints=[
                Endpoint(
                    name='one',
                    type=nested,
                    target_resource_id=profiles[1].id,
                    geo_mapping=['GEO-AF'],
                ),
                Endpoint(
                    name='two',
                    type=nested,
                    target_resource_id=profiles[2].id,
                    geo_mapping=['WORLD'],
                ),
            ],
        )))

        # test that the record and ATM profile gets created
        tm_sync = provider._tm_client.profiles.create_or_update
        create = provider._dns_client.record_sets.create_or_update
        provider._apply_Create(Create(record))
        self.assertEqual(tm_sync.call_count, len(profiles) + 1)
        create.assert_called_once()

        # test broken alias
        azrecord = RecordSet(
            ttl=60, target_resource=SubResource(id=None))
        azrecord.name = record.name or '@'
        azrecord.type = f'Microsoft.Network/dnszones/{record._type}'
        record2 = provider._populate_record(zone, azrecord)
        self.assertEqual(record2.values, ['255.255.255.255'])

        # test that same record gets populated back from traffic managers
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value = profiles
        provider._populate_traffic_managers()
        azrecord = RecordSet(
            ttl=60,
            target_resource=SubResource(id=profiles[-1].id),
        )
        azrecord.name = record.name or '@'
        azrecord.type = f'Microsoft.Network/dnszones/{record._type}'
        record2 = provider._populate_record(zone, azrecord)
        self.assertEqual(record2.dynamic._data(), record.dynamic._data())

        # test that extra changes doesn't show any changes
        desired = Zone(zone.name, sub_zones=[])
        desired.add_record(record)
        changes = provider._extra_changes(zone, desired, [])
        self.assertEqual(len(changes), 0)

    def test_dynamic_AAAA(self):
        provider = self._get_provider()
        external = 'Microsoft.Network/trafficManagerProfiles/externalEndpoints'

        record = Record.new(zone, 'foo', data={
            'type': 'AAAA',
            'ttl': 60,
            'values': ['1::1', '2::2'],
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [
                            {'value': '1::1'},
                            {'value': '2::2'},
                        ],
                    },
                },
                'rules': [
                    {'pool': 'one'},
                ],
            }
        })
        profiles = provider._generate_traffic_managers(record)

        self.assertEqual(len(profiles), 1)
        self.assertTrue(_profile_is_match(profiles[0], Profile(
            name='foo--unit--tests-AAAA',
            traffic_routing_method='Weighted',
            dns_config=DnsConfig(
                relative_name='foo--unit--tests-aaaa', ttl=record.ttl),
            monitor_config=_get_monitor(record),
            endpoints=[
                Endpoint(
                    name='one--1--1--default--',
                    type=external,
                    target='1::1',
                    weight=1,
                ),
                Endpoint(
                    name='one--2--2--default--',
                    type=external,
                    target='2::2',
                    weight=1,
                ),
            ],
        )))

        # test that the record and ATM profile gets created
        tm_sync = provider._tm_client.profiles.create_or_update
        create = provider._dns_client.record_sets.create_or_update
        provider._apply_Create(Create(record))
        # A dynamic record can only have 1 profile
        tm_sync.assert_called_once()
        create.assert_called_once()

        # test broken alias
        azrecord = RecordSet(
            ttl=60, target_resource=SubResource(id=None))
        azrecord.name = record.name or '@'
        azrecord.type = f'Microsoft.Network/dnszones/{record._type}'
        record2 = provider._populate_record(zone, azrecord)
        self.assertEqual(record2.values, ['::1'])

        # test that same record gets populated back from traffic managers
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value = profiles
        azrecord = RecordSet(
            ttl=60,
            target_resource=SubResource(id=profiles[-1].id),
        )
        azrecord.name = record.name or '@'
        azrecord.type = f'Microsoft.Network/dnszones/{record._type}'
        record2 = provider._populate_record(zone, azrecord)
        self.assertEqual(record2.dynamic._data(), record.dynamic._data())

        # test that extra changes doesn't show any changes
        desired = Zone(zone.name, sub_zones=[])
        desired.add_record(record)
        changes = provider._extra_changes(zone, desired, [])
        self.assertEqual(len(changes), 0)

    def test_sync_traffic_managers(self):
        provider, zone, record = self._get_dynamic_package()
        provider._populate_traffic_managers()

        tm_sync = provider._tm_client.profiles.create_or_update

        prefix = 'foo--unit--tests'
        expected_seen = {
            prefix, f'{prefix}-pool-two', f'{prefix}-rule-one',
            f'{prefix}-rule-two',
        }

        # test no change
        profiles = provider._generate_traffic_managers(record)
        seen = provider._sync_traffic_managers(profiles)
        self.assertEqual(seen, expected_seen)
        tm_sync.assert_not_called()

        # test that changing weight causes update API call
        dynamic = record.dynamic._data()
        dynamic['pools']['two']['values'][0]['weight'] = 14
        data = {
            'type': 'CNAME',
            'ttl': record.ttl,
            'value': record.value,
            'dynamic': dynamic,
            'octodns': record._octodns,
        }
        new_record = Record.new(zone, record.name, data)
        tm_sync.reset_mock()
        profiles = provider._generate_traffic_managers(new_record)
        seen2 = provider._sync_traffic_managers(profiles)
        self.assertEqual(seen2, expected_seen)
        tm_sync.assert_called_once()

        # test that new profile was successfully inserted in cache
        new_profile = provider._get_tm_profile_by_name(f'{prefix}-pool-two')
        self.assertEqual(new_profile.endpoints[0].weight, 14)

    def test_sync_traffic_managers_duplicate(self):
        provider, zone, record = self._get_dynamic_package()
        tm_sync = provider._tm_client.profiles.create_or_update

        # change and duplicate profiles
        profile = self._get_tm_profiles(provider)[0]
        profile.name = 'changing_this_to_trigger_sync'
        provider._sync_traffic_managers([profile, profile])

        # it should only be called once for duplicate profiles
        tm_sync.assert_called_once()

    def test_find_traffic_managers(self):
        provider, zone, record = self._get_dynamic_package()

        # insert a non-matching profile
        sample_profile = self._get_tm_profiles(provider)[0]
        # dummy record for generating suffix
        record2 = Record.new(zone, record.name + '2', data={
            'type': record._type,
            'ttl': record.ttl,
            'value': record.value,
        })
        prefix2 = _root_traffic_manager_name(record2)
        tm_id = provider._profile_name_to_id
        extra_profile = Profile(
            id=tm_id(f'{prefix2}-pool-random'),
            name=f'{prefix2}-pool-random',
            traffic_routing_method='Weighted',
            dns_config=sample_profile.dns_config,
            monitor_config=sample_profile.monitor_config,
            endpoints=sample_profile.endpoints,
        )
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value.append(extra_profile)
        provider._populate_traffic_managers()

        # implicitly asserts that non-matching profile is not included
        prefix = _root_traffic_manager_name(record)
        self.assertEqual(provider._find_traffic_managers(record), {
            prefix, f'{prefix}-pool-two', f'{prefix}-rule-one',
            f'{prefix}-rule-two',
        })

    def test_traffic_manager_gc(self):
        provider, zone, record = self._get_dynamic_package()
        provider._populate_traffic_managers()

        profiles = provider._find_traffic_managers(record)
        profile_delete_mock = provider._tm_client.profiles.delete

        provider._traffic_managers_gc(record, profiles)
        profile_delete_mock.assert_not_called()

        profile_delete_mock.reset_mock()
        remove = list(profiles)[3]
        profiles.discard(remove)

        provider._traffic_managers_gc(record, profiles)
        profile_delete_mock.assert_has_calls(
            [call(provider._resource_group, remove)]
        )

    def test_apply(self):
        provider = self._get_provider()

        expected_n = len(octo_records)
        half = int(expected_n / 2)
        changes = [Create(r) for r in octo_records[:half]] + \
            [Update(r, r) for r in octo_records[half:]]
        deletes = [Delete(r) for r in octo_records]

        self.assertEquals(expected_n, provider.apply(Plan(None, zone,
                                                     changes, True)))
        self.assertEquals(expected_n, provider.apply(Plan(zone, zone,
                                                     deletes, True)))

    def test_apply_create_dynamic(self):
        provider = self._get_provider()

        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value = []

        tm_sync = provider._tm_client.profiles.create_or_update

        record = self._get_dynamic_record(zone)

        profiles = self._get_tm_profiles(provider)

        provider._apply_Create(Create(record))
        # create was called as many times as number of profiles required for
        # the dynamic record
        self.assertEqual(tm_sync.call_count, len(profiles))

        create = provider._dns_client.record_sets.create_or_update
        create.assert_called_once()

    def test_apply_update_dynamic(self):
        # existing is simple, new is dynamic
        provider = self._get_provider()
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value = []
        profiles = self._get_tm_profiles(provider)
        dynamic_record = self._get_dynamic_record(zone)
        simple_record = Record.new(zone, dynamic_record.name, data={
            'type': 'CNAME',
            'ttl': 3600,
            'value': 'cname.unit.tests.',
        })
        change = Update(simple_record, dynamic_record)
        provider._apply_Update(change)
        tm_sync, dns_update, tm_delete = (
            provider._tm_client.profiles.create_or_update,
            provider._dns_client.record_sets.create_or_update,
            provider._tm_client.profiles.delete
        )
        self.assertEqual(tm_sync.call_count, len(profiles))
        dns_update.assert_called_once()
        tm_delete.assert_not_called()

        # existing is dynamic, new is simple
        provider, existing, dynamic_record = self._get_dynamic_package()
        profiles = self._get_tm_profiles(provider)
        change = Update(dynamic_record, simple_record)
        provider._apply_Update(change)
        tm_sync, dns_update, tm_delete = (
            provider._tm_client.profiles.create_or_update,
            provider._dns_client.record_sets.create_or_update,
            provider._tm_client.profiles.delete
        )
        tm_sync.assert_not_called()
        dns_update.assert_called_once()
        self.assertEqual(tm_delete.call_count, len(profiles))

        # both are dynamic, healthcheck port is changed
        provider, existing, dynamic_record = self._get_dynamic_package()
        profiles = self._get_tm_profiles(provider)
        dynamic_record2 = self._get_dynamic_record(existing)
        dynamic_record2._octodns['healthcheck']['port'] += 1
        change = Update(dynamic_record, dynamic_record2)
        provider._apply_Update(change)
        tm_sync, dns_update, tm_delete = (
            provider._tm_client.profiles.create_or_update,
            provider._dns_client.record_sets.create_or_update,
            provider._tm_client.profiles.delete
        )
        self.assertEqual(tm_sync.call_count, len(profiles))
        dns_update.assert_not_called()
        tm_delete.assert_not_called()

        # both are dynamic, extra profile should be deleted
        provider, existing, dynamic_record = self._get_dynamic_package()
        sample_profile = self._get_tm_profiles(provider)[0]
        tm_id = provider._profile_name_to_id
        root_profile_name = _root_traffic_manager_name(dynamic_record)
        extra_profile = Profile(
            id=tm_id(f'{root_profile_name}-pool-random'),
            name=f'{root_profile_name}-pool-random',
            traffic_routing_method='Weighted',
            dns_config=sample_profile.dns_config,
            monitor_config=sample_profile.monitor_config,
            endpoints=sample_profile.endpoints,
        )
        tm_list = provider._tm_client.profiles.list_by_resource_group
        tm_list.return_value.append(extra_profile)
        change = Update(dynamic_record, dynamic_record)
        provider._apply_Update(change)
        tm_sync, dns_update, tm_delete = (
            provider._tm_client.profiles.create_or_update,
            provider._dns_client.record_sets.create_or_update,
            provider._tm_client.profiles.delete
        )
        tm_sync.assert_not_called()
        dns_update.assert_not_called()
        tm_delete.assert_called_once()

        # both are dynamic but alias is broken
        provider, existing, record1 = self._get_dynamic_package()
        azrecord = RecordSet(
            ttl=record1.ttl, target_resource=SubResource(id=None))
        azrecord.name = record1.name or '@'
        azrecord.type = f'Microsoft.Network/dnszones/{record1._type}'

        record2 = provider._populate_record(zone, azrecord)
        self.assertEqual(record2.value, 'iam.invalid.')

        change = Update(record2, record1)
        provider._apply_Update(change)
        tm_sync, dns_update, tm_delete = (
            provider._tm_client.profiles.create_or_update,
            provider._dns_client.record_sets.create_or_update,
            provider._tm_client.profiles.delete
        )
        tm_sync.assert_not_called()
        dns_update.assert_called_once()
        tm_delete.assert_not_called()

    def test_apply_update_dynamic_A(self):
        # existing is simple, new is dynamic
        provider = self._get_provider()
        simple_record = Record.new(zone, 'foo', data={
            'type': 'A',
            'ttl': 3600,
            'values': ['1.1.1.1', '2.2.2.2'],
        })
        dynamic_record = Record.new(zone, simple_record.name, data={
            'type': 'A',
            'ttl': 60,
            'values': ['1.1.1.1'],
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [
                            {'value': '8.8.8.8'},
                            {'value': '4.4.4.4'},
                        ],
                        'fallback': 'two',
                    },
                    'two': {
                        'values': [{'value': '9.9.9.9'}],
                    },
                },
                'rules': [
                    {'geos': ['AF'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            }
        })
        num_tms = len(provider._generate_traffic_managers(dynamic_record))
        change = Update(simple_record, dynamic_record)
        provider._apply_Update(change)
        tm_sync, dns_update, tm_delete = (
            provider._tm_client.profiles.create_or_update,
            provider._dns_client.record_sets.create_or_update,
            provider._tm_client.profiles.delete
        )
        # sync is called once for each profile, plus 1 at the end for nested
        # endpoints to workaround A/AAAA nesting limitation in Azure
        self.assertEqual(tm_sync.call_count, num_tms + 1)
        dns_update.assert_called_once()
        tm_delete.assert_not_called()

        # both are dynamic, healthcheck port is changed to trigger sync on
        # all profiles
        provider = self._get_provider()
        dynamic_record2 = Record.new(zone, dynamic_record.name, data={
            'type': dynamic_record._type,
            'ttl': 300,
            'values': dynamic_record.values,
            'dynamic': dynamic_record.dynamic._data(),
            'octodns': {
                'healthcheck': {'port': 4433},
            }
        })
        change = Update(dynamic_record, dynamic_record2)
        provider._apply_Update(change)
        tm_sync, dns_update, tm_delete = (
            provider._tm_client.profiles.create_or_update,
            provider._dns_client.record_sets.create_or_update,
            provider._tm_client.profiles.delete
        )
        # sync is called once for each profile, extra call at the end is not
        # needed when existing dynamic record is already aliased to its root
        # profile
        self.assertEqual(tm_sync.call_count, num_tms)
        dns_update.assert_not_called()
        tm_delete.assert_not_called()

    def test_apply_update_dynamic_A_singluar(self):
        # existing is simple, new is dynamic that needs only one profile
        provider = self._get_provider()
        simple_record = Record.new(zone, 'foo', data={
            'type': 'A',
            'ttl': 3600,
            'values': ['1.1.1.1', '2.2.2.2'],
        })
        dynamic_record = Record.new(zone, simple_record.name, data={
            'type': 'A',
            'ttl': 60,
            'values': ['1.1.1.1'],
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [
                            {'value': '8.8.8.8'},
                            {'value': '1.1.1.1'},
                        ],
                    },
                },
                'rules': [
                    {'pool': 'one'},
                ],
            }
        })
        num_tms = len(provider._generate_traffic_managers(dynamic_record))
        self.assertEqual(num_tms, 1)
        change = Update(simple_record, dynamic_record)
        provider._apply_Update(change)
        tm_sync, dns_update, tm_delete = (
            provider._tm_client.profiles.create_or_update,
            provider._dns_client.record_sets.create_or_update,
            provider._tm_client.profiles.delete
        )
        self.assertEqual(tm_sync.call_count, num_tms)
        dns_update.assert_called_once()
        tm_delete.assert_not_called()

    def test_apply_delete_dynamic(self):
        provider, existing, record = self._get_dynamic_package()
        provider._populate_traffic_managers()
        profiles = self._get_tm_profiles(provider)
        change = Delete(record)
        provider._apply_Delete(change)
        dns_delete, tm_delete = (
            provider._dns_client.record_sets.delete,
            provider._tm_client.profiles.delete
        )
        dns_delete.assert_called_once()
        self.assertEqual(tm_delete.call_count, len(profiles))

    def test_create_zone(self):
        provider = self._get_provider()

        changes = []
        for i in octo_records:
            changes.append(Create(i))
        desired = Zone('unit2.test.', [])

        err_msg = 'The Resource \'Microsoft.Network/dnszones/unit2.test\' '
        err_msg += 'under resource group \'mock_rg\' was not found.'
        _get = provider._dns_client.zones.get
        _get.side_effect = CloudError(Mock(status=404), err_msg)

        expected_n = len(octo_records)
        self.assertEquals(expected_n, provider.apply(Plan(None, desired,
                                                          changes, True)))

    def test_check_zone_no_create(self):
        provider = self._get_provider()

        rs = []
        recordSet = RecordSet(a_records=[ARecord(ipv4_address='1.1.1.1')])
        recordSet.name, recordSet.ttl, recordSet.type = 'a1', 0, 'A'
        rs.append(recordSet)
        recordSet = RecordSet(a_records=[ARecord(ipv4_address='1.1.1.1'),
                                         ARecord(ipv4_address='2.2.2.2')])
        recordSet.name, recordSet.ttl, recordSet.type = 'a2', 1, 'A'
        rs.append(recordSet)

        record_list = provider._dns_client.record_sets.list_by_dns_zone
        record_list.return_value = rs

        err_msg = 'The Resource \'Microsoft.Network/dnszones/unit3.test\' '
        err_msg += 'under resource group \'mock_rg\' was not found.'
        _get = provider._dns_client.zones.get
        _get.side_effect = CloudError(Mock(status=404), err_msg)

        exists = provider.populate(Zone('unit3.test.', []))
        self.assertFalse(exists)

        self.assertEquals(len(zone.records), 0)
