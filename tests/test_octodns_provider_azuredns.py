#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from octodns.record import Create, Delete, Record, Update
from octodns.provider.azuredns import _AzureRecord, AzureProvider
from octodns.zone import Zone

from azure.mgmt.dns.models import ARecord, AaaaRecord, CnameRecord, MxRecord, \
    SrvRecord, NsRecord, PtrRecord, TxtRecord, Zone as AzureZone

from octodns.zone import Zone

from unittest import TestCase
import sys


class Test_AzureRecord(TestCase):
    zone = Zone(name='unit.tests.', sub_zones=[])
    octo_records = []
    octo_records.append(Record.new(zone, '', {
        'ttl': 0,
        'type': 'A',
        'values': ['1.2.3.4', '10.10.10.10']
    }))
    octo_records.append(Record.new(zone, 'a', {
        'ttl': 1,
        'type': 'A',
        'values': ['1.2.3.4', '1.1.1.1'],
    }))
    octo_records.append(Record.new(zone, 'aa', {
        'ttl': 9001,
        'type': 'A',
        'values': ['1.2.4.3']
    }))
    octo_records.append(Record.new(zone, 'aaa', {
        'ttl': 2,
        'type': 'A',
        'values': ['1.1.1.3']
    }))
    octo_records.append(Record.new(zone, 'cname', {
        'ttl': 3,
        'type': 'CNAME',
        'value': 'a.unit.tests.',
    }))
    octo_records.append(Record.new(zone, '', {
        'ttl': 3,
        'type': 'MX',
        'values': [{
            'priority': 10,
            'value': 'mx1.unit.tests.',
        }, {
            'priority': 20,
            'value': 'mx2.unit.tests.',
        }]
    }))
    octo_records.append(Record.new(zone, '', {
        'ttl': 4,
        'type': 'NS',
        'values': ['ns1.unit.tests.', 'ns2.unit.tests.'],
    }))
    octo_records.append(Record.new(zone, '', {
        'ttl': 5,
        'type': 'NS',
        'value': 'ns1.unit.tests.',
    }))
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
        }]
    }))

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
    _base5.relative_record_set_name = '@'
    _base5.record_type = 'MX'
    _base5.params['ttl'] = 3
    _base5.params['mx_records'] = [MxRecord(10, 'mx1.unit.tests.'),
                                   MxRecord(20, 'mx2.unit.tests.')]
    azure_records.append(_base5)

    _base6 = _AzureRecord('TestAzure', octo_records[6])
    _base6.zone_name = 'unit.tests'
    _base6.relative_record_set_name = '@'
    _base6.record_type = 'NS'
    _base6.params['ttl'] = 4
    _base6.params['ns_records'] = [NsRecord('ns1.unit.tests.'),
                                   NsRecord('ns2.unit.tests.')]
    azure_records.append(_base6)

    _base7 = _AzureRecord('TestAzure', octo_records[7])
    _base7.zone_name = 'unit.tests'
    _base7.relative_record_set_name = '@'
    _base7.record_type = 'NS'
    _base7.params['ttl'] = 5
    _base7.params['ns_records'] = [NsRecord('ns1.unit.tests.')]
    azure_records.append(_base7)

    _base8 = _AzureRecord('TestAzure', octo_records[8])
    _base8.zone_name = 'unit.tests'
    _base8.relative_record_set_name = '_srv._tcp'
    _base8.record_type = 'SRV'
    _base8.params['ttl'] = 6
    _base8.params['srv_records'] = [SrvRecord(10, 20, 30, 'foo-1.unit.tests.'),
                                    SrvRecord(12, 30, 30, 'foo-2.unit.tests.')]
    azure_records.append(_base8)

    def test_azure_record(self):
        assert(len(self.azure_records) == len(self.octo_records))
        for i in range(len(self.azure_records)):
            octo = _AzureRecord('TestAzure', self.octo_records[i])
            assert(self.azure_records[i]._equals(octo))


class TestAzureDnsProvider(TestCase):
    def test_populate(self):
        pass  # placeholder
