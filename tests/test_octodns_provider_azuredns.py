#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from octodns.record import Create, Delete, Record
from octodns.provider.azuredns import _AzureRecord, AzureProvider, \
    _check_endswith_dot, _parse_azure_type
from octodns.zone import Zone
from octodns.provider.base import Plan

from azure.mgmt.dns.models import ARecord, AaaaRecord, CaaRecord, \
    CnameRecord, MxRecord, SrvRecord, NsRecord, PtrRecord, TxtRecord, \
    RecordSet, SoaRecord, Zone as AzureZone
from msrestazure.azure_exceptions import CloudError

from unittest import TestCase
from mock import Mock, patch


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

azure_records = []
_base0 = _AzureRecord('TestAzure', octo_records[0])
_base0.zone_name = 'unit.tests'
_base0.relative_record_set_name = '@'
_base0.record_type = 'A'
_base0.params['ttl'] = 0
_base0.params['arecords'] = [ARecord(ipv4_address='1.2.3.4'),
                             ARecord(ipv4_address='10.10.10.10')]
azure_records.append(_base0)

_base1 = _AzureRecord('TestAzure', octo_records[1])
_base1.zone_name = 'unit.tests'
_base1.relative_record_set_name = 'a'
_base1.record_type = 'A'
_base1.params['ttl'] = 1
_base1.params['arecords'] = [ARecord(ipv4_address='1.2.3.4'),
                             ARecord(ipv4_address='1.1.1.1')]
azure_records.append(_base1)

_base2 = _AzureRecord('TestAzure', octo_records[2])
_base2.zone_name = 'unit.tests'
_base2.relative_record_set_name = 'aa'
_base2.record_type = 'A'
_base2.params['ttl'] = 9001
_base2.params['arecords'] = ARecord(ipv4_address='1.2.4.3')
azure_records.append(_base2)

_base3 = _AzureRecord('TestAzure', octo_records[3])
_base3.zone_name = 'unit.tests'
_base3.relative_record_set_name = 'aaa'
_base3.record_type = 'A'
_base3.params['ttl'] = 2
_base3.params['arecords'] = ARecord(ipv4_address='1.1.1.3')
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


class Test_AzureRecord(TestCase):
    def test_azure_record(self):
        assert(len(azure_records) == len(octo_records))
        for i in range(len(azure_records)):
            octo = _AzureRecord('TestAzure', octo_records[i])
            assert(azure_records[i]._equals(octo))


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


class TestAzureDnsProvider(TestCase):
    def _provider(self):
        return self._get_provider('mock_spc', 'mock_dns_client')

    @patch('octodns.provider.azuredns.DnsManagementClient')
    @patch('octodns.provider.azuredns.ServicePrincipalCredentials')
    def _get_provider(self, mock_spc, mock_dns_client):
        '''Returns a mock AzureProvider object to use in testing.

            :param mock_spc: placeholder
            :type  mock_spc: str
            :param mock_dns_client: placeholder
            :type  mock_dns_client: str

            :type return: AzureProvider
        '''
        return AzureProvider('mock_id', 'mock_client', 'mock_key',
                             'mock_directory', 'mock_sub', 'mock_rg')

    def test_populate_records(self):
        provider = self._get_provider()

        rs = []
        recordSet = RecordSet(arecords=[ARecord(ipv4_address='1.1.1.1')])
        recordSet.name, recordSet.ttl, recordSet.type = 'a1', 0, 'A'
        rs.append(recordSet)
        recordSet = RecordSet(arecords=[ARecord(ipv4_address='1.1.1.1'),
                                        ARecord(ipv4_address='2.2.2.2')])
        recordSet.name, recordSet.ttl, recordSet.type = 'a2', 1, 'A'
        rs.append(recordSet)
        aaaa1 = AaaaRecord(ipv6_address='1:1ec:1::1')
        recordSet = RecordSet(aaaa_records=[aaaa1])
        recordSet.name, recordSet.ttl, recordSet.type = 'aaaa1', 2, 'AAAA'
        rs.append(recordSet)
        aaaa2 = AaaaRecord(ipv6_address='1:1ec:1::2')
        recordSet = RecordSet(aaaa_records=[aaaa1,
                                            aaaa2])
        recordSet.name, recordSet.ttl, recordSet.type = 'aaaa2', 3, 'AAAA'
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
        rs.append(recordSet)
        recordSet = RecordSet(cname_record=None)
        recordSet.name, recordSet.ttl, recordSet.type = 'cname2', 6, 'CNAME'
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
        recordSet = RecordSet(ptr_records=[PtrRecord(ptrdname=None)])
        recordSet.name, recordSet.ttl, recordSet.type = 'ptr2', 12, 'PTR'
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
        rs.append(recordSet)
        recordSet = RecordSet(txt_records=[TxtRecord(value='sample text1'),
                                           TxtRecord(value='sample text2')])
        recordSet.name, recordSet.ttl, recordSet.type = 'txt2', 16, 'TXT'
        rs.append(recordSet)
        recordSet = RecordSet(soa_record=[SoaRecord()])
        recordSet.name, recordSet.ttl, recordSet.type = '', 17, 'SOA'
        rs.append(recordSet)

        record_list = provider._dns_client.record_sets.list_by_dns_zone
        record_list.return_value = rs

        exists = provider.populate(zone)
        self.assertTrue(exists)

        self.assertEquals(len(zone.records), 18)

    def test_populate_zone(self):
        provider = self._get_provider()

        zone_list = provider._dns_client.zones.list_by_resource_group
        zone_list.return_value = [AzureZone(location='global'),
                                  AzureZone(location='global')]

        provider._populate_zones()

        self.assertEquals(len(provider._azure_zones), 1)

    def test_bad_zone_response(self):
        provider = self._get_provider()

        _get = provider._dns_client.zones.get
        _get.side_effect = CloudError(Mock(status=404), 'Azure Error')
        trip = False
        try:
            provider._check_zone('unit.test', create=False)
        except CloudError:
            trip = True
        self.assertEquals(trip, True)

    def test_apply(self):
        provider = self._get_provider()

        changes = []
        deletes = []
        for i in octo_records:
            changes.append(Create(i))
            deletes.append(Delete(i))

        self.assertEquals(18, provider.apply(Plan(None, zone,
                                                  changes, True)))
        self.assertEquals(18, provider.apply(Plan(zone, zone,
                                                  deletes, True)))

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

        self.assertEquals(18, provider.apply(Plan(None, desired, changes,
                                                  True)))

    def test_check_zone_no_create(self):
        provider = self._get_provider()

        rs = []
        recordSet = RecordSet(arecords=[ARecord(ipv4_address='1.1.1.1')])
        recordSet.name, recordSet.ttl, recordSet.type = 'a1', 0, 'A'
        rs.append(recordSet)
        recordSet = RecordSet(arecords=[ARecord(ipv4_address='1.1.1.1'),
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
