#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals
	
from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.dns.models import *

from collections import defaultdict
# from incf.countryutils.transformations import cca_to_ctca2 TODO: add geo sup.
import logging
import re

from ..record import Record, Update
from .base import BaseProvider

# Only made for A records. will have to adjust for more generic params types
class _AzureRecord(object):
    def __init__(self, resource_group_name, record, values=None)
        self.resource_group_name = resource_group_name
        self.zone_name = record.zone.name
        self.relative_record_set_name = record.name
        self.record_type = record._type
        
        type_name = '{}records'.format(self.record_type)
        class_name = '{}'.format(self.record_type).capitalize() + 
                     'Record'.format(self.record_type)
        _values = [record._process_values]
        self.params = {'ttl':record.ttl or 1800, \
                       type_name:[eval(class_name)(value) for value in _values] or []}
        


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
	
	# TODO. Will add support as project progresses.
	SUPPORTS_GEO = False
	
    def __init__(self, id, client_id, key, directory_id, sub_id, \
            resource_group, *args, **kwargs):
        self.log = logging.getLogger('AzureProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, client_id=%s, '
                       'key=***, directory_id:%s', id, client_id, directory_id)
        super(AzureProvider, self).__init__(id, *args, **kwargs)
		
        credentials = ServicePrincipalCredentials(
            client_id = client_id, secret = key, tenant = directory_id
        )
        self._dns_client = DnsManagementClient(credentials, sub_id)
        self._resource_group = resource_group

        
        self._azure_zones = None 
        self._azure_records = {} # this is populated through populate()
		
        # TODO: health checks a la route53.
		
		
		
    # TODO: add support for all types. First skeleton: add A.
    def supports(self, record):
        return record._type == 'A'
		
    @property
    def azure_zones(self):
    # TODO: return zones. will be created by populate()
        
    # Given a zone name, returns the zone id. If DNE, creates it.
    def _get_zone_id(self, name):
    
    
    def populate(self, zone, target):
        self._azure_records = {}
    
        for record in zone.records:
    
    
    def _apply_Create(self, change):
        new = change.new
        ar = self._get_azure_record(new)
        
        create = self._dns_client.record_sets.create_or_update
        create(ar.resource_group_name, ar.zone_name, ar.relative_record_set_name \ 
            ar.record_type, ar.params)
    
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
    