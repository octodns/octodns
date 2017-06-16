#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals
	
from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.dns import DnsManagementClient


from collections import defaultdict
# from incf.countryutils.transformations import cca_to_ctca2 TODO: add geo sup.
import logging
import re

from ..record import Record, Update
from .base import BaseProvider

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
		
		
	def _apply(self, plan):
	
