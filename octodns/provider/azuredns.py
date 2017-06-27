#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.dns.models import ARecord, AaaaRecord, CnameRecord, MxRecord, \
    SrvRecord, NsRecord, PtrRecord, TxtRecord, Zone

from functools import reduce

import logging
from ..record import Record
from .base import BaseProvider


class _AzureRecord(object):
    ''' Wrapper for OctoDNS record.
        azuredns.py:
        class: octodns.provider.azuredns._AzureRecord
        An _AzureRecord is easily accessible to Azure DNS Management library
        functions and is used to wrap all relevant data to create a record in
        Azure.
    '''

    def __init__(self, resource_group, record, values=None):
        '''
            :param resource_group: The name of resource group in Azure
            :type  resource_group: str
            :param record: An OctoDNS record
            :type  record: ..record.Record
            :param values: Parameters for a record. eg IP address, port, domain
                           name, etc. Values usually read from record.data
            :type  values: {'values': [...]} or {'value': [...]}

            :type return: _AzureRecord
        '''
        self.resource_group = resource_group
        self.zone_name = record.zone.name[0:len(record.zone.name) - 1]
        self.relative_record_set_name = record.name or '@'
        self.record_type = record._type

        data = values or record.data
        format_u_s = '' if record._type == 'A' else '_'
        key_name = '{}{}records'.format(self.record_type, format_u_s).lower()
        class_name = '{}'.format(self.record_type).capitalize() + \
                     'Record'.format(self.record_type)

        self.params = getattr(self, '_params_for_{}'.format(record._type))
        self.params = self.params(data, key_name, eval(class_name))
        self.params['ttl'] = record.ttl

    def _params(self, data, key_name, azure_class):
        return {key_name: [azure_class(v) for v in data['values']]} \
            if 'values' in data else {key_name: [azure_class(data['value'])]}

    _params_for_A = _params
    _params_for_AAAA = _params
    _params_for_NS = _params
    _params_for_PTR = _params
    _params_for_TXT = _params

    def _params_for_SRV(self, data, key_name, azure_class):
        params = []
        if 'values' in data:
            for vals in data['values']:
                params.append(azure_class(vals['priority'],
                                          vals['weight'],
                                          vals['port'],
                                          vals['target']))
        else:
            params.append(azure_class(data['value']['priority'],
                                      data['value']['weight'],
                                      data['value']['port'],
                                      data['value']['target']))
        return {key_name: params}

    def _params_for_MX(self, data, key_name, azure_class):
        params = []
        if 'values' in data:
            for vals in data['values']:
                params.append(azure_class(vals['priority'],
                                          vals['value']))
        else:
            params.append(azure_class(data['value']['priority'],
                                      data['value']['value']))
        return {key_name: params}

    def _params_for_CNAME(self, data, key_name, azure_class):
        return {'cname_record': CnameRecord(data['value'])}

    def _equals(self, b):
        def parse_dict(params):
            vals = []
            for char in params:
                if char != 'ttl':
                    list_records = params[char]
                    try:
                        for record in list_records:
                            vals.append(record.__dict__)
                    except:
                        vals.append(list_records.__dict__)
            vals.sort()
            return vals

        return (self.resource_group == b.resource_group) & \
               (self.zone_name == b.zone_name) & \
               (self.record_type == b.record_type) & \
               (self.params['ttl'] == b.params['ttl']) & \
               (parse_dict(self.params) == parse_dict(b.params)) & \
               (self.relative_record_set_name == b.relative_record_set_name)

    def __str__(self):
        string = 'Zone: {}; '.format(self.zone_name)
        string += 'Name: {}; '.format(self.relative_record_set_name)
        string += 'Type: {}; '.format(self.record_type)
        string += 'Ttl: {}; '.format(self.params['ttl'])
        for char in self.params:
            if char != 'ttl':
                try:
                    for rec in self.params[char]:
                        string += 'Record: {}; '.format(rec.__dict__)
                except:
                    string += 'Record: {}; '.format(self.params[char].__dict__)
        return string


class AzureProvider(BaseProvider):
    '''
    Azure DNS Provider

    azuredns.py:
        class: octodns.provider.azuredns.AzureProvider
        # Current support of authentication of access to Azure services only
        # includes using a Service Principal:
        # https://docs.microsoft.com/en-us/azure/azure-resource-manager/
        #                        resource-group-create-service-principal-portal
        # The Azure Active Directory Application ID (aka client ID) req:
        client_id:
        # Authentication Key Value req:
        key:
        # Directory ID (referred to tenant ID) req:
        directory_id:
        # Subscription ID req:
        sub_id:
        # Resource Group name req:
        resource_group:

        TODO: change config file to use env vars instead of hard-coded keys

        personal notes: testing: test authentication vars located in
                /home/t-hehwan/vars.txt
    '''
    SUPPORTS_GEO = False
    SUPPORTS = set(('A', 'AAAA', 'CNAME', 'MX', 'NS', 'PTR', 'SRV', 'TXT'))

    def __init__(self, id, client_id, key, directory_id, sub_id,
                 resource_group, *args, **kwargs):
        self.log = logging.getLogger('AzureProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, client_id=%s, '
                       'key=***, directory_id:%s', id, client_id, directory_id)
        super(AzureProvider, self).__init__(id, *args, **kwargs)

        credentials = ServicePrincipalCredentials(
            client_id, secret=key, tenant=directory_id
        )
        self._dns_client = DnsManagementClient(credentials, sub_id)
        self._resource_group = resource_group
        self._azure_zones = set()

    def _populate_zones(self):
        self.log.debug('azure_zones: loading')
        list_zones = self._dns_client.zones.list_by_resource_group
        for zone in list_zones(self._resource_group):
            self._azure_zones.add(zone.name)

    def _check_zone(self, name, create=False):
        '''
            Checks whether a zone specified in a source exist in Azure server.
            Note that Azure zones omit end '.' eg: contoso.com vs contoso.com.
            Returns the name if it exists.

            :param name: Name of a zone to checks
            :type  name: str
            :param create: If True, creates the zone of that name.
            :type  create: bool

            :type return: str or None
        '''
        self.log.debug('_check_zone: name=%s', name)
        try:
            if name in self._azure_zones:
                return name
            if self._dns_client.zones.get(self._resource_group, name):
                self._azure_zones.add(name)
                return name
        except:  # TODO: figure out what location should be
            if create:
                try:
                    self.log.debug('_check_zone:no matching zone; creating %s',
                                   name)
                    create_zone = self._dns_client.zones.create_or_update
                    if create_zone(self._resource_group, name, Zone('global')):
                        return name
                except:
                    raise
        return None

    def populate(self, zone, target=False, lenient=False):
        '''
            Required function of manager.py.

            Special notes for Azure. Azure zone names omit final '.'
            Azure record names for '' are represented by '@'
            Azure records created through online interface may have null values
            (eg, no IP address for A record). Specific quirks such as these are
            responsible for any strange parsing.

            :param zone: A dns zone
            :type  zone: octodns.zone.Zone
            :param target: Checks if Azure is source or target of config.
                           Currently only supports as a target. Does not use.
            :type  target: bool


            TODO: azure interface allows null values. If this attempts to
            populate with them, will fail. add safety check (simply delete
            records with null values?)

            :type return: void
        '''
        zone_name = zone.name[0:len(zone.name) - 1]
        self.log.debug('populate: name=%s', zone_name)
        before = len(zone.records)

        self._populate_zones()
        if self._check_zone(zone_name):
            for typ in self.SUPPORTS:
                records = self._dns_client.record_sets.list_by_type
                for azrecord in records(self._resource_group, zone_name, typ):
                    record_name = azrecord.name if azrecord.name != '@' else ''
                    data = getattr(self, '_data_for_{}'.format(typ))(azrecord)
                    data['type'] = typ
                    data['ttl'] = azrecord.ttl

                    record = Record.new(zone, record_name, data, source=self)
                    zone.add_record(record)

        self.log.info('populate: found %s records', len(zone.records) - before)

    def _data_for_A(self, azrecord):
        return {'values': [ar.ipv4_address for ar in azrecord.arecords]}

    def _data_for_AAAA(self, azrecord):
        return {'values': [ar.ipv6_address for ar in azrecord.aaaa_records]}

    def _data_for_TXT(self, azrecord):
        return {'values': [reduce((lambda a, b: a + b), ar.value)
                           for ar in azrecord.txt_records]}

    def _data_for_CNAME(self, azrecord):  # TODO: see TODO in pop comment.
        try:
            val = azrecord.cname_record.cname
            if not val.endswith('.'):
                val += '.'
            return {'value': val}
        except:
            return {'value': '.'}  # TODO: this is a bad fix. but octo checks
            # that cnames have trailing '.' while azure allows creating cnames
            # on the online interface with no value.

    def _data_for_PTR(self, azrecord):  # TODO: see TODO in population comment.
        try:
            val = azrecord.ptr_records[0].ptdrname
            if not val.endswith('.'):
                val += '.'
            return {'value': val}
        except:
            return {'value': '.'}

    def _data_for_MX(self, azrecord):
        return {'values': [{'priority': ar.preference, 'value': ar.exchange}
                           for ar in azrecord.mx_records]
                }

    def _data_for_SRV(self, azrecord):
        return {'values': [{'priority': ar.priority, 'weight': ar.weight,
                            'port': ar.port, 'target': ar.target}
                           for ar in azrecord.srv_records]
                }

    def _data_for_NS(self, azrecord):  # TODO: see TODO in population comment.
        def period_validate(string):
            return string if string.endswith('.') else string + '.'
        vals = [ar.nsdname for ar in azrecord.ns_records]
        return {'values': [period_validate(val) for val in vals]}

    def _apply_Create(self, change):
        '''A record from change must be created.

            :param change: a change object
            :type  change: octodns.record.Change

            :type return: void
        '''
        ar = _AzureRecord(self._resource_group, change.new)
        create = self._dns_client.record_sets.create_or_update

        create(resource_group_name=ar.resource_group,
               zone_name=ar.zone_name,
               relative_record_set_name=ar.relative_record_set_name,
               record_type=ar.record_type,
               parameters=ar.params)

    def _apply_Delete(self, change):
        ar = _AzureRecord(self._resource_group, change.existing)
        delete = self._dns_client.record_sets.delete

        delete(self._resource_group, ar.zone_name, ar.relative_record_set_name,
               ar.record_type)

    def _apply_Update(self, change):
        self._apply_Create(change)

    def _apply(self, plan):
        '''
            Required function of manager.py

            :param plan: Contains the zones and changes to be made
            :type  plan: octodns.provider.base.Plan

            :type return: void
        '''
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        azure_zone_name = desired.name[0:len(desired.name) - 1]
        self._check_zone(azure_zone_name, create=True)

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name))(change)
