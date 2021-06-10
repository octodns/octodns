#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict

from azure.identity import ClientSecretCredential
from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.trafficmanager import TrafficManagerManagementClient

from azure.mgmt.dns.models import ARecord, AaaaRecord, CaaRecord, \
    CnameRecord, MxRecord, SrvRecord, NsRecord, PtrRecord, TxtRecord, Zone
from azure.mgmt.trafficmanager.models import Profile, DnsConfig, \
    MonitorConfig, Endpoint, MonitorConfigCustomHeadersItem

import logging
from functools import reduce
from ..record import Record, Update, GeoCodes
from .base import BaseProvider


class AzureException(Exception):
    pass


def escape_semicolon(s):
    assert s
    return s.replace(';', '\\;')


def unescape_semicolon(s):
    assert s
    return s.replace('\\;', ';')


def azure_chunked_value(val):
    CHUNK_SIZE = 255
    val_replace = val.replace('"', '\\"')
    value = unescape_semicolon(val_replace)
    if len(val) > CHUNK_SIZE:
        vs = [value[i:i + CHUNK_SIZE]
              for i in range(0, len(value), CHUNK_SIZE)]
    else:
        vs = value
    return vs


def azure_chunked_values(s):
    values = []
    for v in s:
        values.append(azure_chunked_value(v))
    return values


class _AzureRecord(object):
    '''Wrapper for OctoDNS record for AzureProvider to make dns_client calls.

        azuredns.py:
        class: octodns.provider.azuredns._AzureRecord
        An _AzureRecord is easily accessible to Azure DNS Management library
        functions and is used to wrap all relevant data to create a record in
        Azure.
    '''
    TYPE_MAP = {
        'A': ARecord,
        'AAAA': AaaaRecord,
        'CAA': CaaRecord,
        'CNAME': CnameRecord,
        'MX': MxRecord,
        'SRV': SrvRecord,
        'NS': NsRecord,
        'PTR': PtrRecord,
        'TXT': TxtRecord
    }

    def __init__(self, resource_group, record, delete=False,
                 traffic_manager=None):
        '''Constructor for _AzureRecord.

            Notes on Azure records: An Azure record set has the form
            RecordSet(name=<...>, type=<...>, a_records=[...],
            aaaa_records=[...], ...)
            When constructing an azure record as done in self._apply_Create,
            the argument parameters for an A record would be
            parameters={'ttl': <int>, 'a_records': [ARecord(<str ip>),]}.
            As another example for CNAME record:
            parameters={'ttl': <int>, 'cname_record': CnameRecord(<str>)}.

            Below, key_name and class_name are the dictionary key and Azure
            Record class respectively.

            :param resource_group: The name of resource group in Azure
            :type  resource_group: str
            :param record: An OctoDNS record
            :type  record: ..record.Record
            :param delete: If true, omit data parsing; not needed to delete
            :type  delete: bool

            :type return: _AzureRecord
        '''
        self.log = logging.getLogger('AzureRecord')

        self.resource_group = resource_group
        self.zone_name = record.zone.name[:-1]
        self.relative_record_set_name = record.name or '@'
        self.record_type = record._type
        self._record = record
        self.traffic_manager = traffic_manager

        if delete:
            return

        # Refer to function docstring for key_name and class_name.
        key_name = '{}_records'.format(self.record_type).lower()
        if record._type == 'CNAME':
            key_name = key_name[:-1]
        azure_class = self.TYPE_MAP[self.record_type]

        params_for = getattr(self, '_params_for_{}'.format(record._type))
        self.params = params_for(record.data, key_name, azure_class)
        self.params['ttl'] = record.ttl

    def _params_for_A(self, data, key_name, azure_class):
        try:
            values = data['values']
        except KeyError:
            values = [data['value']]
        return {key_name: [azure_class(ipv4_address=v) for v in values]}

    def _params_for_AAAA(self, data, key_name, azure_class):
        try:
            values = data['values']
        except KeyError:
            values = [data['value']]
        return {key_name: [azure_class(ipv6_address=v) for v in values]}

    def _params_for_CAA(self, data, key_name, azure_class):
        params = []
        if 'values' in data:
            for vals in data['values']:
                params.append(azure_class(flags=vals['flags'],
                                          tag=vals['tag'],
                                          value=vals['value']))
        else:  # Else there is a singular data point keyed by 'value'.
            params.append(azure_class(flags=data['value']['flags'],
                                      tag=data['value']['tag'],
                                      value=data['value']['value']))
        return {key_name: params}

    def _params_for_CNAME(self, data, key_name, azure_class):
        if self._record.dynamic and self.traffic_manager:
            return {'target_resource': self.traffic_manager}

        return {key_name: azure_class(cname=data['value'])}

    def _params_for_MX(self, data, key_name, azure_class):
        params = []
        if 'values' in data:
            for vals in data['values']:
                params.append(azure_class(preference=vals['preference'],
                                          exchange=vals['exchange']))
        else:  # Else there is a singular data point keyed by 'value'.
            params.append(azure_class(preference=data['value']['preference'],
                                      exchange=data['value']['exchange']))
        return {key_name: params}

    def _params_for_SRV(self, data, key_name, azure_class):
        params = []
        if 'values' in data:
            for vals in data['values']:
                params.append(azure_class(priority=vals['priority'],
                                          weight=vals['weight'],
                                          port=vals['port'],
                                          target=vals['target']))
        else:  # Else there is a singular data point keyed by 'value'.
            params.append(azure_class(priority=data['value']['priority'],
                                      weight=data['value']['weight'],
                                      port=data['value']['port'],
                                      target=data['value']['target']))
        return {key_name: params}

    def _params_for_NS(self, data, key_name, azure_class):
        try:
            values = data['values']
        except KeyError:
            values = [data['value']]
        return {key_name: [azure_class(nsdname=v) for v in values]}

    def _params_for_PTR(self, data, key_name, azure_class):
        try:
            values = data['values']
        except KeyError:
            values = [data['value']]
        return {key_name: [azure_class(ptrdname=v) for v in values]}

    def _params_for_TXT(self, data, key_name, azure_class):

        params = []
        try:  # API for TxtRecord has list of str, even for singleton
            values = [v for v in azure_chunked_values(data['values'])]
        except KeyError:
            values = [azure_chunked_value(data['value'])]

        for v in values:
            if isinstance(v, list):
                params.append(azure_class(value=v))
            else:
                params.append(azure_class(value=[v]))
        return {key_name: params}

    def _equals(self, b):
        '''Checks whether two records are equal by comparing all fields.
            :param b: Another _AzureRecord object
            :type  b: _AzureRecord

            :type return: bool
        '''

        def key_dict(d):
            return sum([hash('{}:{}'.format(k, v)) for k, v in d.items()])

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
            vals.sort(key=key_dict)
            return vals

        return (self.resource_group == b.resource_group) & \
               (self.zone_name == b.zone_name) & \
               (self.record_type == b.record_type) & \
               (self.params['ttl'] == b.params['ttl']) & \
               (parse_dict(self.params) == parse_dict(b.params)) & \
               (self.relative_record_set_name == b.relative_record_set_name)


def _check_endswith_dot(string):
    return string if string.endswith('.') else string + '.'


def _parse_azure_type(string):
    '''Converts string representing an Azure RecordSet type to usual type.

        :param string: the Azure type. eg: <Microsoft.Network/dnszones/A>
        :type  string: str

        :type return: str
    '''
    return string.split('/')[-1]


def _root_traffic_manager_name(record):
    # ATM names can only have letters, numbers and hyphens
    # replace dots with double hyphens to ensure unique mapping,
    # hoping that real life FQDNs won't have double hyphens
    return record.fqdn[:-1].replace('.', '--')


def _rule_traffic_manager_name(pool, record):
    prefix = _root_traffic_manager_name(record)
    return '{}-rule-{}'.format(prefix, pool)


def _pool_traffic_manager_name(pool, record):
    prefix = _root_traffic_manager_name(record)
    return '{}-pool-{}'.format(prefix, pool)


def _get_monitor(record):
    monitor = MonitorConfig(
        protocol=record.healthcheck_protocol,
        port=record.healthcheck_port,
        path=record.healthcheck_path,
    )
    host = record.healthcheck_host
    if host:
        monitor.custom_headers = [MonitorConfigCustomHeadersItem(
            name='Host', value=host
        )]
    return monitor


def _profile_is_match(have, desired):
    if have is None or desired is None:
        return False

    log = logging.getLogger('azuredns._profile_is_match').debug

    def false(have, desired, name=None):
        prefix = 'profile={}'.format(name) if name else ''
        attr = have.__class__.__name__
        log('%s have.%s = %s', prefix, attr, have)
        log('%s desired.%s = %s', prefix, attr, desired)
        return False

    # compare basic attributes
    if have.name != desired.name or \
       have.traffic_routing_method != desired.traffic_routing_method or \
       len(have.endpoints) != len(desired.endpoints):
        return false(have, desired)

    # compare dns config
    dns_have = have.dns_config
    dns_desired = desired.dns_config
    if dns_have.ttl != dns_desired.ttl or \
       dns_have.relative_name is None or \
       dns_desired.relative_name is None or \
       dns_have.relative_name != dns_desired.relative_name:
        return false(dns_have, dns_desired, have.name)

    # compare monitoring configuration
    monitor_have = have.monitor_config
    monitor_desired = desired.monitor_config
    if monitor_have.protocol != monitor_desired.protocol or \
       monitor_have.port != monitor_desired.port or \
       monitor_have.path != monitor_desired.path or \
       monitor_have.custom_headers != monitor_desired.custom_headers:
        return false(monitor_have, monitor_desired, have.name)

    # compare endpoints
    method = have.traffic_routing_method
    if method == 'Priority':
        have_endpoints = sorted(have.endpoints, key=lambda e: e.priority)
        desired_endpoints = sorted(desired.endpoints,
                                   key=lambda e: e.priority)
    elif method == 'Weighted':
        have_endpoints = sorted(have.endpoints, key=lambda e: e.target)
        desired_endpoints = sorted(desired.endpoints, key=lambda e: e.target)
    else:
        have_endpoints = have.endpoints
        desired_endpoints = desired.endpoints
    endpoints = zip(have_endpoints, desired_endpoints)
    for have_endpoint, desired_endpoint in endpoints:
        if have_endpoint.name != desired_endpoint.name or \
           have_endpoint.type != desired_endpoint.type:
            return false(have_endpoint, desired_endpoint, have.name)
        target_type = have_endpoint.type.split('/')[-1]
        if target_type == 'externalEndpoints':
            # compare value, weight, priority
            if have_endpoint.target != desired_endpoint.target:
                return false(have_endpoint, desired_endpoint, have.name)
            if method == 'Weighted' and \
               have_endpoint.weight != desired_endpoint.weight:
                return false(have_endpoint, desired_endpoint, have.name)
        elif target_type == 'nestedEndpoints':
            # compare targets
            if have_endpoint.target_resource_id != \
               desired_endpoint.target_resource_id:
                return false(have_endpoint, desired_endpoint, have.name)
            # compare geos
            if method == 'Geographic':
                have_geos = sorted(have_endpoint.geo_mapping)
                desired_geos = sorted(desired_endpoint.geo_mapping)
                if have_geos != desired_geos:
                    return false(have_endpoint, desired_endpoint, have.name)
        else:
            # unexpected, give up
            return False

    return True


class AzureProvider(BaseProvider):
    '''
    Azure DNS Provider

    azuredns.py:
        class: octodns.provider.azuredns.AzureProvider
        # Current support of authentication of access to Azure services only
        # includes using a Service Principal:
        # https://docs.microsoft.com/en-us/azure/azure-resource-manager/
        #                        resource-group-create-service-principal-portal
        # The Azure Active Directory Application ID (aka client ID):
        client_id:
        # Authentication Key Value: (note this should be secret)
        key:
        # Directory ID (aka tenant ID):
        directory_id:
        # Subscription ID:
        sub_id:
        # Resource Group name:
        resource_group:
        # All are required to authenticate.

        Example config file with variables:
            "
            ---
            providers:
              config:
                class: octodns.provider.yaml.YamlProvider
                directory: ./config (example path to directory of zone files)
              azuredns:
                class: octodns.provider.azuredns.AzureProvider
                client_id: env/AZURE_APPLICATION_ID
                key: env/AZURE_AUTHENTICATION_KEY
                directory_id: env/AZURE_DIRECTORY_ID
                sub_id: env/AZURE_SUBSCRIPTION_ID
                resource_group: 'TestResource1'

            zones:
              example.com.:
                sources:
                  - config
                targets:
                  - azuredns
            "
        The first four variables above can be hidden in environment variables
        and octoDNS will automatically search for them in the shell. It is
        possible to also hard-code into the config file: eg, resource_group.

        Please read https://github.com/octodns/octodns/pull/706 for an overview
        of how dynamic records are designed and caveats of using them.
    '''
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = True
    SUPPORTS = set(('A', 'AAAA', 'CAA', 'CNAME', 'MX', 'NS', 'PTR', 'SRV',
                    'TXT'))

    def __init__(self, id, client_id, key, directory_id, sub_id,
                 resource_group, *args, **kwargs):
        self.log = logging.getLogger('AzureProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, client_id=%s, '
                       'key=***, directory_id:%s', id, client_id, directory_id)
        super(AzureProvider, self).__init__(id, *args, **kwargs)

        # Store necessary initialization params
        self._dns_client_handle = None
        self._dns_client_client_id = client_id
        self._dns_client_key = key
        self._dns_client_directory_id = directory_id
        self._dns_client_subscription_id = sub_id
        self.__dns_client = None
        self.__tm_client = None

        self._resource_group = resource_group
        self._azure_zones = set()
        self._traffic_managers = dict()

    @property
    def _dns_client(self):
        if self.__dns_client is None:
            # Azure's logger spits out a lot of debug messages at 'INFO'
            # level, override it by re-assigning `info` method to `debug`
            # (ugly hack until I find a better way)
            logger_name = 'azure.core.pipeline.policies.http_logging_policy'
            logger = logging.getLogger(logger_name)
            logger.info = logger.debug
            self.__dns_client = DnsManagementClient(
                credential=ClientSecretCredential(
                    client_id=self._dns_client_client_id,
                    client_secret=self._dns_client_key,
                    tenant_id=self._dns_client_directory_id,
                    logger=logger,
                ),
                subscription_id=self._dns_client_subscription_id,
            )
        return self.__dns_client

    @property
    def _tm_client(self):
        if self.__tm_client is None:
            self.__tm_client = TrafficManagerManagementClient(
                ServicePrincipalCredentials(
                    self._dns_client_client_id,
                    secret=self._dns_client_key,
                    tenant=self._dns_client_directory_id,
                ),
                self._dns_client_subscription_id,
            )
        return self.__tm_client

    def _populate_zones(self):
        self.log.debug('azure_zones: loading')
        list_zones = self._dns_client.zones.list_by_resource_group
        for zone in list_zones(self._resource_group):
            self._azure_zones.add(zone.name.rstrip('.'))

    def _check_zone(self, name, create=False):
        '''Checks whether a zone specified in a source exist in Azure server.

            Note that Azure zones omit end '.' eg: contoso.com vs contoso.com.
            Returns the name if it exists.

            :param name: Name of a zone to checks
            :type  name: str
            :param create: If True, creates the zone of that name.
            :type  create: bool

            :type return: str or None
        '''
        self.log.debug('_check_zone: name=%s create=%s', name, create)
        # Check if the zone already exists in our set
        if name in self._azure_zones:
            return name
        # If not, and its time to create, lets do it.
        if create:
            self.log.debug('_check_zone:no matching zone; creating %s', name)
            create_zone = self._dns_client.zones.create_or_update
            create_zone(self._resource_group, name, Zone(location='global'))
            self._azure_zones.add(name)
            return name
        else:
            # Else return nothing (aka false)
            return

    def _populate_traffic_managers(self):
        self.log.debug('traffic managers: loading')
        list_profiles = self._tm_client.profiles.list_by_resource_group
        for profile in list_profiles(self._resource_group):
            self._traffic_managers[profile.id] = profile
        # link nested profiles in advance for convenience
        for _, profile in self._traffic_managers.items():
            self._populate_nested_profiles(profile)

    def _populate_nested_profiles(self, profile):
        for ep in profile.endpoints:
            target_id = ep.target_resource_id
            if target_id and target_id in self._traffic_managers:
                target = self._traffic_managers[target_id]
                ep.target_resource = self._populate_nested_profiles(target)
        return profile

    def _get_tm_profile_by_id(self, resource_id):
        if not self._traffic_managers:
            self._populate_traffic_managers()
        return self._traffic_managers.get(resource_id)

    def _profile_name_to_id(self, name):
        return '/subscriptions/' + self._dns_client_subscription_id + \
            '/resourceGroups/' + self._resource_group + \
            '/providers/Microsoft.Network/trafficManagerProfiles/' + \
            name

    def _get_tm_profile_by_name(self, name):
        profile_id = self._profile_name_to_id(name)
        return self._get_tm_profile_by_id(profile_id)

    def _get_tm_for_dynamic_record(self, record):
        name = _root_traffic_manager_name(record)
        return self._get_tm_profile_by_name(name)

    def populate(self, zone, target=False, lenient=False):
        '''Required function of manager.py to collect records from zone.

            Special notes for Azure.
            Azure zone names omit final '.'
            Azure root records names are represented by '@'. OctoDNS uses ''
            Azure records created through online interface may have null values
            (eg, no IP address for A record).
            Azure online interface allows constructing records with null values
            which are destroyed by _apply.

            Specific quirks such as these are responsible for any non-obvious
            parsing in this function and the functions '_params_for_*'.

            :param zone: A dns zone
            :type  zone: octodns.zone.Zone
            :param target: Checks if Azure is source or target of config.
                           Currently only supports as a target. Unused.
            :type  target: bool
            :param lenient: Unused. Check octodns.manager for usage.
            :type  lenient: bool

            :type return: void
        '''
        self.log.debug('populate: name=%s', zone.name)

        exists = False
        before = len(zone.records)

        zone_name = zone.name[:-1]
        self._populate_zones()

        records = self._dns_client.record_sets.list_by_dns_zone
        if self._check_zone(zone_name):
            exists = True
            for azrecord in records(self._resource_group, zone_name):
                typ = _parse_azure_type(azrecord.type)
                if typ not in self.SUPPORTS:
                    continue

                record = self._populate_record(zone, azrecord, lenient)
                zone.add_record(record, lenient=lenient)

        self.log.info('populate: found %s records, exists=%s',
                      len(zone.records) - before, exists)
        return exists

    def _populate_record(self, zone, azrecord, lenient=False):
        record_name = azrecord.name if azrecord.name != '@' else ''
        typ = _parse_azure_type(azrecord.type)

        data_for = getattr(self, '_data_for_{}'.format(typ))
        data = data_for(azrecord)
        data['type'] = typ
        data['ttl'] = azrecord.ttl
        return Record.new(zone, record_name, data, source=self,
                          lenient=lenient)

    def _data_for_A(self, azrecord):
        return {'values': [ar.ipv4_address for ar in azrecord.a_records]}

    def _data_for_AAAA(self, azrecord):
        return {'values': [ar.ipv6_address for ar in azrecord.aaaa_records]}

    def _data_for_CAA(self, azrecord):
        return {'values': [{'flags': ar.flags,
                            'tag': ar.tag,
                            'value': ar.value}
                           for ar in azrecord.caa_records]}

    def _data_for_CNAME(self, azrecord):
        '''Parsing data from Azure DNS Client record call
            :param azrecord: a return of a call to list azure records
            :type  azrecord: azure.mgmt.dns.models.RecordSet

            :type  return: dict
        '''
        if azrecord.cname_record is None:
            if azrecord.target_resource.id:
                return self._data_for_dynamic(azrecord)
            else:
                # dynamic record alias is broken, return dummy value and apply
                # will likely overwrite/fix it
                return {'value': 'iam.invalid.'}

        return {'value': _check_endswith_dot(azrecord.cname_record.cname)}

    def _data_for_MX(self, azrecord):
        return {'values': [{'preference': ar.preference,
                            'exchange': ar.exchange}
                           for ar in azrecord.mx_records]}

    def _data_for_NS(self, azrecord):
        vals = [ar.nsdname for ar in azrecord.ns_records]
        return {'values': [_check_endswith_dot(val) for val in vals]}

    def _data_for_PTR(self, azrecord):
        ptrdname = azrecord.ptr_records[0].ptrdname
        return {'value': _check_endswith_dot(ptrdname)}

    def _data_for_SRV(self, azrecord):
        return {'values': [{'priority': ar.priority, 'weight': ar.weight,
                            'port': ar.port, 'target': ar.target}
                           for ar in azrecord.srv_records]}

    def _data_for_TXT(self, azrecord):
        return {'values': [escape_semicolon(reduce((lambda a, b: a + b),
                                                   ar.value))
                           for ar in azrecord.txt_records]}

    def _data_for_dynamic(self, azrecord):
        default = set()
        pools = defaultdict(lambda: {'fallback': None, 'values': []})
        rules = []

        # top level profile
        root_profile = self._get_tm_profile_by_id(azrecord.target_resource.id)
        if root_profile.traffic_routing_method != 'Geographic':
            # This record does not use geo fencing, so we skip the Geographic
            # profile hop; let's pretend to be a geo-profile's only endpoint
            geo_ep = Endpoint(target_resource_id=root_profile.id)
            geo_ep.target_resource = root_profile
            endpoints = [geo_ep]
        else:
            endpoints = root_profile.endpoints

        for geo_ep in endpoints:
            rule = {}

            # resolve list of regions
            geo_map = list(geo_ep.geo_mapping or [])
            if geo_map and geo_map != ['WORLD']:
                if 'GEO-ME' in geo_map:
                    # Azure treats Middle East as a separate group, but
                    # its part of Asia in octoDNS, so we need to remove GEO-ME
                    # if GEO-AS is also in the list
                    # Throw exception otherwise, it should not happen if the
                    # profile was generated by octoDNS
                    if 'GEO-AS' not in geo_map:
                        msg = 'Profile={} for record {}: '.format(
                            root_profile.name, azrecord.fqdn)
                        msg += 'Middle East (GEO-ME) is not supported by ' + \
                               'octoDNS. It needs to be either paired ' + \
                               'with Asia (GEO-AS) or expanded into ' + \
                               'individual list of countries.'
                        raise AzureException(msg)
                    geo_map.remove('GEO-ME')
                geos = rule.setdefault('geos', [])
                for code in geo_map:
                    if code.startswith('GEO-'):
                        # continent
                        if code == 'GEO-AP':
                            # Azure uses Australia/Pacific (AP) instead of
                            # Oceania https://docs.microsoft.com/en-us/azure/
                            #                                traffic-manager/
                            #              traffic-manager-geographic-regions
                            geos.append('OC')
                        else:
                            geos.append(code[len('GEO-'):])
                    elif '-' in code:
                        # state
                        country, province = code.split('-', 1)
                        country = GeoCodes.country_to_code(country)
                        geos.append('{}-{}'.format(country, province))
                    else:
                        # country
                        geos.append(GeoCodes.country_to_code(code))

            # build fallback chain from second level priority profile
            if geo_ep.target_resource_id:
                target = geo_ep.target_resource
                if target.traffic_routing_method == 'Priority':
                    rule_endpoints = target.endpoints
                    rule_endpoints.sort(key=lambda e: e.priority)
                else:
                    # Weighted
                    geo_ep.name = target.endpoints[0].name.split('--', 1)[0]
                    rule_endpoints = [geo_ep]
            else:
                # this geo directly points to the default, so we skip the
                # Priority profile hop and directly use an external endpoint;
                # let's pretend to be a Priority profile's only endpoint
                rule_endpoints = [geo_ep]

            pool = None
            for rule_ep in rule_endpoints:
                pool_name = rule_ep.name

                # last/default pool
                if pool_name.endswith('--default--'):
                    default.add(rule_ep.target)
                    if pool_name == '--default--':
                        # this should be the last one, so let's break here
                        break
                    # last pool is a single value pool and its value is same
                    # as record's default value
                    pool_name = pool_name[:-len('--default--')]

                # set first priority endpoint as the rule's primary pool
                if 'pool' not in rule:
                    rule['pool'] = pool_name

                if pool:
                    # set current pool as fallback of the previous pool
                    pool['fallback'] = pool_name

                if pool_name in pools:
                    # we've already populated the pool
                    continue

                # populate the pool from Weighted profile
                # these should be leaf node entries with no further nesting
                pool = pools[pool_name]
                endpoints = []

                if rule_ep.target_resource_id:
                    # third (and last) level weighted RR profile
                    endpoints = rule_ep.target_resource.endpoints
                else:
                    # single-value pool, so we skip the Weighted profile hop
                    # and directly use an external endpoint; let's pretend to
                    # be a Weighted profile's only endpoint
                    endpoints = [rule_ep]

                for pool_ep in endpoints:
                    val = pool_ep.target
                    pool['values'].append({
                        'value': _check_endswith_dot(val),
                        'weight': pool_ep.weight or 1,
                    })
                    if pool_ep.name.endswith('--default--'):
                        default.add(val)

            rules.append(rule)

        # Order and convert to a list
        default = sorted(default)

        data = {
            'dynamic': {
                'pools': pools,
                'rules': rules,
            },
            'value': _check_endswith_dot(default[0]),
        }

        return data

    def _extra_changes(self, existing, desired, changes):
        changed = set()

        # Abort if there are non-CNAME dynamic records
        for change in changes:
            record = change.record
            changed.add(record)
            typ = record._type
            dynamic = getattr(record, 'dynamic', False)
            if dynamic and typ != 'CNAME':
                msg = '{}: Dynamic records in Azure must be of type CNAME'
                msg = msg.format(record.fqdn)
                raise AzureException(msg)

        log = self.log.info
        seen_profiles = {}
        extra = []
        for record in desired.records:
            if not getattr(record, 'dynamic', False):
                # Already changed, or not dynamic, no need to check it
                continue

            # let's walk through and show what will be changed even if
            # the record is already be in list of changes
            added = (record in changed)

            active = set()
            profiles = self._generate_traffic_managers(record)
            for profile in profiles:
                name = profile.name
                if name in seen_profiles:
                    # exit if a possible collision is detected, even though
                    # we've tried to ensure unique mapping
                    msg = 'Collision in Traffic Manager names detected'
                    msg = '{}: {} and {} both want to use {}'.format(
                        msg, seen_profiles[name], record.fqdn, name)
                    raise AzureException(msg)
                else:
                    seen_profiles[name] = record.fqdn

                active.add(name)
                existing_profile = self._get_tm_profile_by_name(name)
                if not _profile_is_match(existing_profile, profile):
                    log('_extra_changes: Profile name=%s will be synced',
                        name)
                    if not added:
                        extra.append(Update(record, record))
                        added = True

            existing_profiles = self._find_traffic_managers(record)
            for name in existing_profiles - active:
                log('_extra_changes: Profile name=%s will be destroyed', name)
                if not added:
                    extra.append(Update(record, record))
                    added = True

        return extra

    def _generate_tm_profile(self, routing, endpoints, record, label=None):
        # figure out profile name and Traffic Manager FQDN
        name = _root_traffic_manager_name(record)
        if routing == 'Weighted':
            name = _pool_traffic_manager_name(label, record)
        elif routing == 'Priority':
            name = _rule_traffic_manager_name(label, record)

        # set appropriate endpoint types
        endpoint_type_prefix = 'Microsoft.Network/trafficManagerProfiles/'
        for ep in endpoints:
            if ep.target_resource_id:
                ep.type = endpoint_type_prefix + 'nestedEndpoints'
            elif ep.target:
                ep.type = endpoint_type_prefix + 'externalEndpoints'
            else:
                msg = ('Invalid endpoint {} in profile {}, needs to have ' +
                       'either target or target_resource_id').format(
                           ep.name, name)
                raise AzureException(msg)

        # build and return
        return Profile(
            id=self._profile_name_to_id(name),
            name=name,
            traffic_routing_method=routing,
            dns_config=DnsConfig(
                relative_name=name,
                ttl=record.ttl,
            ),
            monitor_config=_get_monitor(record),
            endpoints=endpoints,
            location='global',
        )

    def _convert_tm_to_root(self, profile, record):
        profile.name = _root_traffic_manager_name(record)
        profile.id = self._profile_name_to_id(profile.name)
        profile.dns_config.relative_name = profile.name

        return profile

    def _generate_traffic_managers(self, record):
        traffic_managers = []
        pools = record.dynamic.pools

        default = record.value[:-1]
        profile = self._generate_tm_profile

        geo_endpoints = []
        pool_profiles = {}

        for rule in record.dynamic.rules:
            # Prepare the list of Traffic manager geos
            rule_geos = rule.data.get('geos', [])
            geos = []
            for geo in rule_geos:
                if '-' in geo:
                    # country/state
                    geos.append(geo.split('-', 1)[-1])
                else:
                    # continent
                    if geo == 'AS':
                        # Middle East is part of Asia in octoDNS, but
                        # Azure treats it as a separate "group", so let's
                        # add it in the list of geo mappings. We will drop
                        # it when we later parse the list of regions.
                        geos.append('GEO-ME')
                    elif geo == 'OC':
                        # Azure uses Australia/Pacific (AP) instead of
                        # Oceania
                        geo = 'AP'

                    geos.append('GEO-{}'.format(geo))
            if not geos:
                geos.append('WORLD')

            pool_name = rule.data['pool']
            rule_endpoints = []
            priority = 1
            default_seen = False

            while pool_name:
                # iterate until we reach end of fallback chain
                default_seen = False
                pool = pools[pool_name].data
                if len(pool['values']) > 1:
                    # create Weighted profile for multi-value pool
                    pool_profile = pool_profiles.get(pool_name)
                    if pool_profile is None:
                        endpoints = []
                        for val in pool['values']:
                            target = val['value']
                            # strip trailing dot from CNAME value
                            target = target[:-1]
                            ep_name = '{}--{}'.format(pool_name, target)
                            if target == default:
                                # mark default
                                ep_name += '--default--'
                                default_seen = True
                            endpoints.append(Endpoint(
                                name=ep_name,
                                target=target,
                                weight=val.get('weight', 1),
                            ))
                        pool_profile = profile(
                            'Weighted', endpoints, record, pool_name)
                        traffic_managers.append(pool_profile)
                        pool_profiles[pool_name] = pool_profile

                    # append pool to endpoint list of fallback rule profile
                    rule_endpoints.append(Endpoint(
                        name=pool_name,
                        target_resource_id=pool_profile.id,
                        priority=priority,
                    ))
                else:
                    # Skip Weighted profile hop for single-value pool
                    # append its value as an external endpoint to fallback
                    # rule profile
                    target = pool['values'][0]['value'][:-1]
                    ep_name = pool_name
                    if target == default:
                        # mark default
                        ep_name += '--default--'
                        default_seen = True
                    rule_endpoints.append(Endpoint(
                        name=pool_name,
                        target=target,
                        priority=priority,
                    ))

                priority += 1
                pool_name = pool.get('fallback')

            # append default endpoint unless it is already included in
            # last pool of rule profile
            if not default_seen:
                rule_endpoints.append(Endpoint(
                    name='--default--',
                    target=default,
                    priority=priority,
                ))

            if len(rule_endpoints) > 1:
                # create rule profile with fallback chain
                rule_profile = profile(
                    'Priority', rule_endpoints, record, rule.data['pool'])
                traffic_managers.append(rule_profile)

                # append rule profile to top-level geo profile
                geo_endpoints.append(Endpoint(
                    name='rule-{}'.format(rule.data['pool']),
                    target_resource_id=rule_profile.id,
                    geo_mapping=geos,
                ))
            else:
                # Priority profile has only one endpoint; skip the hop and
                # append its only endpoint to the top-level profile
                rule_ep = rule_endpoints[0]
                if rule_ep.target_resource_id:
                    # point directly to the Weighted pool profile
                    geo_endpoints.append(Endpoint(
                        name='rule-{}'.format(rule.data['pool']),
                        target_resource_id=rule_ep.target_resource_id,
                        geo_mapping=geos,
                    ))
                else:
                    # just add the value of single-value pool
                    geo_endpoints.append(Endpoint(
                        name=rule_ep.name + '--default--',
                        target=rule_ep.target,
                        geo_mapping=geos,
                    ))

        if len(geo_endpoints) == 1 and \
           geo_endpoints[0].geo_mapping == ['WORLD'] and \
           geo_endpoints[0].target_resource_id:
            # Single WORLD rule does not require a Geographic profile, use
            # the target profile as the root profile
            self._convert_tm_to_root(traffic_managers[-1], record)
        else:
            geo_profile = profile('Geographic', geo_endpoints, record)
            traffic_managers.append(geo_profile)

        return traffic_managers

    def _sync_traffic_managers(self, record):
        desired_profiles = self._generate_traffic_managers(record)
        seen = set()

        tm_sync = self._tm_client.profiles.create_or_update
        populate = self._populate_nested_profiles

        for desired in desired_profiles:
            name = desired.name
            if name in seen:
                continue

            existing = self._get_tm_profile_by_name(name)
            if not _profile_is_match(existing, desired):
                self.log.info(
                    '_sync_traffic_managers: Syncing profile=%s', name)
                profile = tm_sync(self._resource_group, name, desired)
                self._traffic_managers[profile.id] = populate(profile)
            else:
                self.log.debug(
                    '_sync_traffic_managers: Skipping profile=%s: up to date',
                    name)
            seen.add(name)

        return seen

    def _find_traffic_managers(self, record):
        tm_prefix = _root_traffic_manager_name(record)

        profiles = set()
        for profile_id in self._traffic_managers:
            # match existing profiles with record's prefix
            name = profile_id.split('/')[-1]
            if name == tm_prefix or \
               name.startswith('{}-pool-'.format(tm_prefix)) or \
               name.startswith('{}-rule-'.format(tm_prefix)):
                profiles.add(name)

        return profiles

    def _traffic_managers_gc(self, record, active_profiles):
        existing_profiles = self._find_traffic_managers(record)

        # delete unused profiles
        for profile_name in existing_profiles - active_profiles:
            self.log.info('_traffic_managers_gc: Deleting profile=%s',
                          profile_name)
            self._tm_client.profiles.delete(self._resource_group, profile_name)

    def _apply_Create(self, change):
        '''A record from change must be created.

            :param change: a change object
            :type  change: octodns.record.Change

            :type return: void
        '''
        record = change.new

        dynamic = getattr(record, 'dynamic', False)
        if dynamic:
            self._sync_traffic_managers(record)

        profile = self._get_tm_for_dynamic_record(record)
        ar = _AzureRecord(self._resource_group, record,
                          traffic_manager=profile)
        create = self._dns_client.record_sets.create_or_update

        create(resource_group_name=ar.resource_group,
               zone_name=ar.zone_name,
               relative_record_set_name=ar.relative_record_set_name,
               record_type=ar.record_type,
               parameters=ar.params)

        self.log.debug('*  Success Create: {}'.format(record))

    def _apply_Update(self, change):
        '''A record from change must be created.

            :param change: a change object
            :type  change: octodns.record.Change

            :type return: void
        '''
        existing = change.existing
        new = change.new
        existing_is_dynamic = getattr(existing, 'dynamic', False)
        new_is_dynamic = getattr(new, 'dynamic', False)

        update_record = True

        if new_is_dynamic:
            active = self._sync_traffic_managers(new)
            # only TTL is configured in record, everything else goes inside
            # traffic managers, so no need to update if TTL is unchanged
            # and existing record is already aliased to its traffic manager
            if existing.ttl == new.ttl and existing_is_dynamic:
                update_record = False

        if update_record:
            profile = self._get_tm_for_dynamic_record(new)
            ar = _AzureRecord(self._resource_group, new,
                              traffic_manager=profile)
            update = self._dns_client.record_sets.create_or_update

            update(resource_group_name=ar.resource_group,
                   zone_name=ar.zone_name,
                   relative_record_set_name=ar.relative_record_set_name,
                   record_type=ar.record_type,
                   parameters=ar.params)

        if new_is_dynamic:
            # let's cleanup unused traffic managers
            self._traffic_managers_gc(new, active)
        elif existing_is_dynamic:
            # cleanup traffic managers when a dynamic record gets
            # changed to a simple record
            self._traffic_managers_gc(existing, set())

        self.log.debug('*  Success Update: {}'.format(new))

    def _apply_Delete(self, change):
        '''A record from change must be deleted.

            :param change: a change object
            :type  change: octodns.record.Change

            :type return: void
        '''
        record = change.record
        ar = _AzureRecord(self._resource_group, record, delete=True)
        delete = self._dns_client.record_sets.delete

        delete(self._resource_group, ar.zone_name, ar.relative_record_set_name,
               ar.record_type)

        if getattr(record, 'dynamic', False):
            self._traffic_managers_gc(record, set())

        self.log.debug('*  Success Delete: {}'.format(record))

    def _apply(self, plan):
        '''Required function of manager.py to actually apply a record change.

            :param plan: Contains the zones and changes to be made
            :type  plan: octodns.provider.base.Plan

            :type return: void
        '''
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        azure_zone_name = desired.name[:len(desired.name) - 1]
        self._check_zone(azure_zone_name, create=True)

        '''
        Force the operation order to be Delete() before all other operations.
        Helps avoid problems in updating
            - a CNAME record into an A record.
            - an A record into a CNAME record.
        '''

        for change in changes:
            class_name = change.__class__.__name__
            if class_name == 'Delete':
                self._apply_Delete(change)

        for change in changes:
            class_name = change.__class__.__name__
            if class_name != 'Delete':
                getattr(self, '_apply_{}'.format(class_name))(change)
