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

from azure.mgmt.dns.models import ARecord, AaaaRecord, CnameRecord, MxRecord, \
    SrvRecord, NsRecord, PtrRecord, TxtRecord, RecordSet, SoaRecord, \
    Zone as AzureZone
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
_base0.params['arecords'] = [ARecord('1.2.3.4'), ARecord('10.10.10.10')]
azure_records.append(_base0)

_base1 = _AzureRecord('TestAzure', octo_records[1])
_base1.zone_name = 'unit.tests'
_base1.relative_record_set_name = 'a'
_base1.record_type = 'A'
_base1.params['ttl'] = 1
_base1.params['arecords'] = [ARecord('1.2.3.4'), ARecord('1.1.1.1')]
azure_records.append(_base1)

_base2 = _AzureRecord('TestAzure', octo_records[2])
_base2.zone_name = 'unit.tests'
_base2.relative_record_set_name = 'aa'
_base2.record_type = 'A'
_base2.params['ttl'] = 9001
_base2.params['arecords'] = ARecord('1.2.4.3')
azure_records.append(_base2)

_base3 = _AzureRecord('TestAzure', octo_records[3])
_base3.zone_name = 'unit.tests'
_base3.relative_record_set_name = 'aaa'
_base3.record_type = 'A'
_base3.params['ttl'] = 2
_base3.params['arecords'] = ARecord('1.1.1.3')
azure_records.append(_base3)

_base4 = _AzureRecord('TestAzure', octo_records[4])
_base4.zone_name = 'unit.tests'
_base4.relative_record_set_name = 'cname'
_base4.record_type = 'CNAME'
_base4.params['ttl'] = 3
_base4.params['cname_record'] = CnameRecord('a.unit.tests.')
azure_records.append(_base4)

_base5 = _AzureRecord('TestAzure', octo_records[5])
_base5.zone_name = 'unit.tests'
_base5.relative_record_set_name = 'mx1'
_base5.record_type = 'MX'
_base5.params['ttl'] = 3
_base5.params['mx_records'] = [MxRecord(10, 'mx1.unit.tests.'),
                               MxRecord(20, 'mx2.unit.tests.')]
azure_records.append(_base5)

_base6 = _AzureRecord('TestAzure', octo_records[6])
_base6.zone_name = 'unit.tests'
_base6.relative_record_set_name = 'mx2'
_base6.record_type = 'MX'
_base6.params['ttl'] = 3
_base6.params['mx_records'] = [MxRecord(10, 'mx1.unit.tests.')]
azure_records.append(_base6)

_base7 = _AzureRecord('TestAzure', octo_records[7])
_base7.zone_name = 'unit.tests'
_base7.relative_record_set_name = '@'
_base7.record_type = 'NS'
_base7.params['ttl'] = 4
_base7.params['ns_records'] = [NsRecord('ns1.unit.tests.'),
                               NsRecord('ns2.unit.tests.')]
azure_records.append(_base7)

_base8 = _AzureRecord('TestAzure', octo_records[8])
_base8.zone_name = 'unit.tests'
_base8.relative_record_set_name = 'foo'
_base8.record_type = 'NS'
_base8.params['ttl'] = 5
_base8.params['ns_records'] = [NsRecord('ns1.unit.tests.')]
azure_records.append(_base8)

_base9 = _AzureRecord('TestAzure', octo_records[9])
_base9.zone_name = 'unit.tests'
_base9.relative_record_set_name = '_srv._tcp'
_base9.record_type = 'SRV'
_base9.params['ttl'] = 6
_base9.params['srv_records'] = [SrvRecord(10, 20, 30, 'foo-1.unit.tests.'),
                                SrvRecord(12, 30, 30, 'foo-2.unit.tests.')]
azure_records.append(_base9)

_base10 = _AzureRecord('TestAzure', octo_records[10])
_base10.zone_name = 'unit.tests'
_base10.relative_record_set_name = '_srv2._tcp'
_base10.record_type = 'SRV'
_base10.params['ttl'] = 7
_base10.params['srv_records'] = [SrvRecord(12, 17, 1, 'srvfoo.unit.tests.')]
azure_records.append(_base10)

_base11 = _AzureRecord('TestAzure', octo_records[11])
_base11.zone_name = 'unit.tests'
_base11.relative_record_set_name = 'txt1'
_base11.record_type = 'TXT'
_base11.params['ttl'] = 8
_base11.params['txt_records'] = [TxtRecord(['txt singleton test'])]
azure_records.append(_base11)

_base12 = _AzureRecord('TestAzure', octo_records[12])
_base12.zone_name = 'unit.tests'
_base12.relative_record_set_name = 'txt2'
_base12.record_type = 'TXT'
_base12.params['ttl'] = 9
_base12.params['txt_records'] = [TxtRecord(['txt multiple test']),
                                 TxtRecord(['txt multiple test 2'])]
azure_records.append(_base12)


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
        recordSet = RecordSet(arecords=[ARecord('1.1.1.1')])
        recordSet.name, recordSet.ttl, recordSet.type = 'a1', 0, 'A'
        rs.append(recordSet)
        recordSet = RecordSet(arecords=[ARecord('1.1.1.1'),
                                        ARecord('2.2.2.2')])
        recordSet.name, recordSet.ttl, recordSet.type = 'a2', 1, 'A'
        rs.append(recordSet)
        recordSet = RecordSet(aaaa_records=[AaaaRecord('1:1ec:1::1')])
        recordSet.name, recordSet.ttl, recordSet.type = 'aaaa1', 2, 'AAAA'
        rs.append(recordSet)
        recordSet = RecordSet(aaaa_records=[AaaaRecord('1:1ec:1::1'),
                                            AaaaRecord('1:1ec:1::2')])
        recordSet.name, recordSet.ttl, recordSet.type = 'aaaa2', 3, 'AAAA'
        rs.append(recordSet)
        recordSet = RecordSet(cname_record=CnameRecord('cname.unit.test.'))
        recordSet.name, recordSet.ttl, recordSet.type = 'cname1', 4, 'CNAME'
        rs.append(recordSet)
        recordSet = RecordSet(cname_record=None)
        recordSet.name, recordSet.ttl, recordSet.type = 'cname2', 5, 'CNAME'
        rs.append(recordSet)
        recordSet = RecordSet(mx_records=[MxRecord(10, 'mx1.unit.test.')])
        recordSet.name, recordSet.ttl, recordSet.type = 'mx1', 6, 'MX'
        rs.append(recordSet)
        recordSet = RecordSet(mx_records=[MxRecord(10, 'mx1.unit.test.'),
                                          MxRecord(11, 'mx2.unit.test.')])
        recordSet.name, recordSet.ttl, recordSet.type = 'mx2', 7, 'MX'
        rs.append(recordSet)
        recordSet = RecordSet(ns_records=[NsRecord('ns1.unit.test.')])
        recordSet.name, recordSet.ttl, recordSet.type = 'ns1', 8, 'NS'
        rs.append(recordSet)
        recordSet = RecordSet(ns_records=[NsRecord('ns1.unit.test.'),
                                          NsRecord('ns2.unit.test.')])
        recordSet.name, recordSet.ttl, recordSet.type = 'ns2', 9, 'NS'
        rs.append(recordSet)
        recordSet = RecordSet(ptr_records=[PtrRecord('ptr1.unit.test.')])
        recordSet.name, recordSet.ttl, recordSet.type = 'ptr1', 10, 'PTR'
        rs.append(recordSet)
        recordSet = RecordSet(ptr_records=[PtrRecord(None)])
        recordSet.name, recordSet.ttl, recordSet.type = 'ptr2', 11, 'PTR'
        rs.append(recordSet)
        recordSet = RecordSet(srv_records=[SrvRecord(1, 2, 3, '1unit.tests.')])
        recordSet.name, recordSet.ttl, recordSet.type = '_srv1._tcp', 12, 'SRV'
        rs.append(recordSet)
        recordSet = RecordSet(srv_records=[SrvRecord(1, 2, 3, '1unit.tests.'),
                                           SrvRecord(4, 5, 6, '2unit.tests.')])
        recordSet.name, recordSet.ttl, recordSet.type = '_srv2._tcp', 13, 'SRV'
        rs.append(recordSet)
        recordSet = RecordSet(txt_records=[TxtRecord('sample text1')])
        recordSet.name, recordSet.ttl, recordSet.type = 'txt1', 14, 'TXT'
        rs.append(recordSet)
        recordSet = RecordSet(txt_records=[TxtRecord('sample text1'),
                                           TxtRecord('sample text2')])
        recordSet.name, recordSet.ttl, recordSet.type = 'txt2', 15, 'TXT'
        rs.append(recordSet)
        recordSet = RecordSet(soa_record=[SoaRecord()])
        recordSet.name, recordSet.ttl, recordSet.type = '', 16, 'SOA'
        rs.append(recordSet)

        record_list = provider._dns_client.record_sets.list_by_dns_zone
        record_list.return_value = rs

        exists = provider.populate(zone)
        self.assertTrue(exists)

        self.assertEquals(len(zone.records), 16)

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

        self.assertEquals(13, provider.apply(Plan(None, zone,
                                                  changes, True)))
        self.assertEquals(13, provider.apply(Plan(zone, zone,
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

        self.assertEquals(13, provider.apply(Plan(None, desired, changes,
                                                  True)))

    def test_check_zone_no_create(self):
        provider = self._get_provider()

        rs = []
        recordSet = RecordSet(arecords=[ARecord('1.1.1.1')])
        recordSet.name, recordSet.ttl, recordSet.type = 'a1', 0, 'A'
        rs.append(recordSet)
        recordSet = RecordSet(arecords=[ARecord('1.1.1.1'),
                                        ARecord('2.2.2.2')])
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
