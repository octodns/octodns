#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals
import sys

from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.dns.models import *

from collections import defaultdict
# from incf.countryutils.transformations import cca_to_ctca2 TODO: add geo sup.
import logging
import re
from ..record import Record, Update
from .base import BaseProvider


#TODO: changes made to master include adding /build, Makefile to .gitignore and 
# making Makefile.
# Only made for A records. will have to adjust for more generic params types
class _AzureRecord(object):
    def __init__(self, resource_group, record, values=None, ttl=1800):
        # print('Here4',file=sys.stderr)
        self.resource_group = resource_group
        self.zone_name = record.zone.name[0:len(record.zone.name)-1] # strips last period
        self.relative_record_set_name = record.name or '@'
        self.record_type = record._type
        
        type_name = '{}records'.format(self.record_type).lower()
        class_name = '{}'.format(self.record_type).capitalize() + \
                     'Record'.format(self.record_type)
        if values == None:
            return
        # TODO: clean up this bit.
        data = values or record.data #This should fail if it gets to record.data? It only returns ttl. TODO
        
        #depending on mult values or not
        #TODO: import explicitly. eval() uses for example ARecord from azure.mgmt.dns.models
        self.params = {}
        try:
            self.params = {'ttl':record.ttl or ttl, \
               type_name:[eval(class_name)(ip) for ip in data['values']] or []}
        except KeyError: # means that doesn't have multiple values but single value
            self.params = {'ttl':record.ttl or ttl, \
               type_name:[eval(class_name)(data['value'])] or []}


    

class AzureProvider(BaseProvider):
    '''
    Azure DNS Provider
    
    azure.py:
        class: octodns.provider.azure.AzureProvider
        # Current support of authentication of access to Azure services only 
        # includes using a Service Principal: 
        # https://docs.microsoft.com/en-us/azure/azure-resource-manager/
        #                        resource-group-create-service-principal-portal
        # The Azure Active Directory Application ID (referred to client ID) req:
        client_id:
        # Authentication Key Value req:
        key:
        # Directory ID (referred to tenant ID) req:
        directory_id:
        # Subscription ID req:
        sub_id:
        # Resource Group name req:
        resource_group:
        
        testing: test authentication vars located in /home/t-hehwan/vars.txt
    '''
    SUPPORTS_GEO = False # TODO. Will add support as project progresses.
    
    def __init__(self, id, client_id, key, directory_id, sub_id, resource_group, *args, **kwargs):
        self.log = logging.getLogger('AzureProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, client_id=%s, '
                'key=***, directory_id:%s', id, client_id, directory_id)
        super(AzureProvider, self).__init__(id, *args, **kwargs)

        credentials = ServicePrincipalCredentials(
        client_id = client_id, secret = key, tenant = directory_id
        )
        self._dns_client = DnsManagementClient(credentials, sub_id)
        self._resource_group = resource_group

        self._azure_zones = None # will be a dictionary. key: name. val: id.
        self._azure_records = {} # will be dict by octodns record, az record

        self._supported_types = ['CNAME', 'A', 'AAAA', 'MX', 'SRV', 'NS', 'PTR']
        # TODO: add TXT

        # TODO: health checks a la route53.


        
    # TODO: add support for all types. First skeleton: add A.
    def supports(self, record):
        return record._type in self._supported_types
        
    @property
    def azure_zones(self):
        if self._azure_zones is None:
            self.log.debug('azure_zones: loading')
            zones = {}
            for zone in self._dns_client.zones.list_by_resource_group(self._resource_group):
                zones[zone.name] = zone.id
            self._azure_zones = zones
        return self._azure_zones
        
    # Given a zone name, returns the zone id. If DNE, creates it.
    def _get_zone_id(self, name, create=False):
        self.log.debug('_get_zone_id: name=%s', name)
        try:
            id = self._dns_client.zones.get(self._resource_group, name)
            self.log.debug('_get_zone_id: id=%s', id)
            return id
        except:
            if create:
                self.log.debug('_get_zone_id: no matching zone; creating %s', name)
                #TODO: write
                return None #placeholder
            return None
        
    # Create a dictionary of record objects by zone and octodns record names
    # TODO: add geo parsing
    def populate(self, zone, target):
        zone_name = zone.name[0:len(zone.name)-1]#Azure zone names do not include suffix .
        self.log.debug('populate: name=%s', zone_name)
        before = len(zone.records)
        zone_id = self._get_zone_id(zone_name) 
        if zone_id:
            #records = defaultdict(list)
            for type in self._supported_types:
                # print('populate. type: {}'.format(type),file=sys.stderr)
                for azrecord in self._dns_client.record_sets.list_by_type(self._resource_group, zone_name, type):
                    # print(azrecord, file=sys.stderr)
                    record_name = azrecord.name if azrecord.name != '@' else ''
                    data = self._type_and_ttl(type, azrecord, 
                           getattr(self, '_data_for_{}'.format(type))(azrecord)) # TODO: azure online interface allows None values. must validate.
                    record = Record.new(zone, record_name, data, source=self)
                    # print('HERE0',file=sys.stderr)
                    zone.add_record(record)
                    self._azure_records[record] = _AzureRecord(self._resource_group, record, data)
        # print('HERE1',file=sys.stderr)
        self.log.info('populate: found %s records', len(zone.records)-before)
        
    # might not need
    def _get_type(azrecord):
        azrecord['type'].split('/')[-1]
        
    def _type_and_ttl(self, type, azrecord, data):
        data['type'] = type
        data['ttl'] = azrecord.ttl
        return data
        
    def _data_for_A(self, azrecord):
        return {'values': [ar.ipv4_address for ar in azrecord.arecords]}
        
    def _data_for_AAAA(self, azrecord):
        return {'values': [ar.ipv6_address for ar in azrecord.aaaa_records]}
        
    def _data_for_TXT(self, azrecord):
        print('azure',file=sys.stderr)
        print([ar.value for ar in azrecord.txt_records], file=sys.stderr)
        print('',file=sys.stderr)
        return {'values': [ar.value for ar in azrecord.txt_records]}

    def _data_for_CNAME(self, azrecord):
        try:
            val = azrecord.cname_record.cname
            if not val.endswith('.'):
                val += '.'
            return {'value': val}
        except:
            return {'value': '.'} #TODO: this is a bad fix. but octo checks that cnames have trailing '.' while azure allows creating cnames on the online interface with no value.
           
    def _data_for_PTR(self, azrecord):
        try:
            val = azrecord.ptr_records[0].ptdrname
            if not val.endswith('.'):
                val += '.'
            return {'value': val}
        except:
            return {'value': '.' } #TODO: this is a bad fix. but octo checks that cnames have trailing '.' while azure allows creating cnames on the online interface with no value.
        
    def _data_for_MX(self, azrecord):
        return {'values': [{'priority':ar.preference,
                            'value':ar.exchange} for ar in azrecord.mx_records]}
                            
    def _data_for_SRV(self, azrecord):
        return {'values': [{'priority': ar.priority,
                        'weight': ar.weight,
                        'port': ar.port,
                        'target': ar.target} for ar in azrecord.srv_records]
        }
        
    def _data_for_NS(self, azrecord):
        def period_validate(string):
            return string if string.endswith('.') else string + '.'
        vals = [ar.nsdname for ar in azrecord.ns_records]
        return {'values': [period_validate(val) for val in vals]}

    def _apply_Create(self, change):
        new = change.new

        #validate that the zone exists.
        #self._get_zone_id(new.name, create=True)
        
        ar = _AzureRecord(self._resource_group, new, new.data)
        
        create = self._dns_client.record_sets.create_or_update
        create(resource_group_name=ar.resource_group, 
               zone_name=ar.zone_name, 
               relative_record_set_name=ar.relative_record_set_name, 
               record_type=ar.record_type, 
               parameters=ar.params)
               
    def _apply_Delete(self, change):
        existing = change.existing
        ar = _AzureRecord(self._resource_group, existing)
        delete = self._dns_client.record_sets.delete
        delete(self._resource_group, ar.zone_name, ar.relative_record_set_name, 
               ar.record_type)
    
    def _apply_Update(self, change):
        self._apply_Delete(change)
        self._apply_Create(change)
    
    # type plan: Plan class from .base
    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name, 
                       len(changes))
        
        # validate that the zone exists. function creates zone if DNE.
        self._get_zone_id(desired.name)
        
        # Some parsing bits to call _mod_Create or _mod_Delete.
        # changes is a list of Delete and Create objects.
        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name))(change)

    
    
    # **********
    # Figuring out what object plan is.
    
    # self._executor = ThreadPoolExecutor(max_workers)
    # futures.append(self._executor.submit(self._populate_and_plan,
                                     # zone_name, sources, targets))
    # plans = [p for f in futures for p in f.results()]
    # type of plans[0] == type of one output of _populate_and_plan
    
    # for target, plan in plans:
        # apply(plan)
        
        
    # type(target) == BaseProvider
    # type(plan) == Plan()
    
    # Plan(existing, desired, changes)
        # existing.type == desired.type == Zone(desired.name, desired.sub_zones)
            # Zone(name, sub_zones) (str and set of strs)
        # changes.type = [Delete/Create]
    

    # Starts with sync in main() of sync.
    # {u'values': ['3.3.3.3', '4.4.4.4'], u'type': 'A', u'ttl': 3600}
    # {u'type': u'A', u'value': [u'3.3.3.3', u'4.4.4.4'], u'ttl': 3600L}