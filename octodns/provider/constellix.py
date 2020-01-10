#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict
from requests import Session
from base64 import b64encode
from ipaddress import ip_address
from six import string_types
import hashlib
import hmac
import logging
import time

from ..record import Record
from .base import BaseProvider


class ConstellixClientException(Exception):
    pass


class ConstellixClientBadRequest(ConstellixClientException):
    def __init__(self, resp):
        super(ConstellixClientBadRequest, self).__init__(
            '\n  - {}'.format('\n  - '.join(resp.json()['errors']))
        )


class ConstellixClientUnauthorized(ConstellixClientException):
    def __init__(self):
        super(ConstellixClientUnauthorized, self).__init__('Unauthorized')


class ConstellixClientNotFound(ConstellixClientException):
    def __init__(self):
        super(ConstellixClientNotFound, self).__init__('Not Found')


class ConstellixClient(object):
    """
    REST client for interacting with Constellix DNS API service
    """
    BASE = 'https://api.dns.constellix.com/v1'

    def __init__(self, api_key, secret_key, ratelimit_delay=0.0):
        """
        Constructor
        :param api_key: string - The user's API key
        :param secret_key: string - The user's secret key that is associated
         with the API key
        :param ratelimit_delay: float - The rate-limit delay in milliseconds
        (i.e. 1 / max_rate or 1 / max_frequency)
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.ratelimit_delay = ratelimit_delay
        self._sess = Session()
        self._domains = None

    @staticmethod
    def current_time():
        """
        calculates the total milliseconds from epoch (UTC)

        Returns:
            string: current UTC time in milliseconds, as a string
        """
        return str(int(round(time.time() * 1000)))

    @staticmethod
    def hmac_hash(secret_key, current_time):
        """
        Calculates the HMAC for the secret key at the current time
        :param secret_key: string - the secret key associated with
        the API key
        :param current_time: string - the number of milliseconds
        from epoch represented as a string
        :return: string - The base-64 encode HMAC
        """
        auth_hash = hmac.new(secret_key.encode('utf-8'),
                             current_time.encode('utf-8'),
                             digestmod=hashlib.sha1).digest()
        return b64encode(auth_hash)

    def create_http_headers(self):
        """
        Creates the HTTP headers required for authentication and making
        requests

        :return:
            Dict: a dictionary holding the key-value pairs for the header
        """
        now = self.current_time()
        hmac_hash = self.hmac_hash(self.secret_key, now)
        token = self.api_key.encode('utf-8') + ":" + hmac_hash + ":" + now

        headers = {
            'Content-Type': 'application/json',
            'x-cns-security-token': token
        }
        return headers

    def _request(self, method, path, params=None, data=None):
        """
        Makes the request against the Constellix DNS REST API service.
        :param method: string - The HTTP method (i.e. GET, PUT, POST, DELETE)
        :param path: string - The path (that is appended to the base path)
        :param params: Dict - The query param key-value pairs
        :param data: Dict - The request body represented as key-value pairs
        :return:
            Response: The response from the server
        """
        headers = self.create_http_headers()

        url = '{}{}'.format(self.BASE, path)
        resp = self._sess.request(
            method, url, headers=headers, params=params, json=data
        )
        if resp.status_code == 400:
            raise ConstellixClientBadRequest(resp)
        if resp.status_code == 401:
            raise ConstellixClientUnauthorized()
        if resp.status_code == 404:
            raise ConstellixClientNotFound()
        resp.raise_for_status()
        time.sleep(self.ratelimit_delay)
        return resp

    def domains(self):
        """
        Retrieves a list of domains associated with the api-key's account
        from the Constellix DNS REST API service.
        :return:
            Dict: Holds the domain names and their associated domain IDs.
        """
        if self._domains is None:   # pragma: no coverage
            zones = []

            resp = self._request('GET', '/domains').json()
            zones += resp

            self._domains = {'{}.'.format(z['name']): z['id'] for z in zones}

        return self._domains

    def domain(self, name):
        """
        Retrieves the domain with the specified name from the the
        Constellix DNS REST API service
        :param name: string - The name of the domain to retrieve
        :return:
            Any: JSON representation of the domain
        """
        domain_name = self.domains().get(name)
        path = '/domains/{}'.format(domain_name)
        return self._request('GET', path).json()

    def domain_create(self, name):
        """
        Request the creation of a domain with the specified name
        :param name: string - The name of the domain to create
        :return:
            Response: The response from the API service
        """
        return self._request(
            'POST',
            '/domains', data={'names': [name]}
        ).json()

    @staticmethod
    def _absolutize_value(value, zone_name):
        """
        Converts the fully-qualified domain name (FQDN) into its absolute
        form by concatenating the sub-domain and the domain. Note that
        the `zone_name` is required to have a trailing dot (otherwise the
        zone object cannot be created).
        :param value: string - The sub-domain name
        :param zone_name: string - The domain name (required dot at end)
        :return:
            string: The absolute version of the FQDN
        """
        if value == '' or value == '.':
            fqdn = zone_name
        elif not value.endswith('.'):
            fqdn = '{}.{}'.format(value, zone_name)
        else:
            fqdn = '{}.{}'.format(value[:-1], zone_name)

        return fqdn

    def records(self, zone_name):
        """
        Retrieves a list of the records attached to the domain
        :param zone_name: string - The domain name
        :return:
            list(dict) - A list of dictionaries where each dictionary
            represents a record.
        """
        zone_id = self.domains().get(zone_name, False)
        path = '/domains/{}/records'.format(zone_id)

        record_list = self._request('GET', path).json()
        for record in record_list:
            # change ANAME records to ALIAS
            if record['type'] == 'ANAME':
                record['type'] = 'ALIAS'

            # change relative values to absolute
            value = record['value']
            if record['type'] in ['ALIAS', 'CNAME', 'MX', 'NS', 'SRV']:

                if isinstance(value, string_types):
                    record['value'] = self._absolutize_value(value,
                                                             zone_name)
                if isinstance(value, list):
                    for v in value:
                        v['value'] = self._absolutize_value(
                            v['value'], zone_name
                        )

            # compress IPv6 addresses
            if record['type'] == 'AAAA':
                for i, v in enumerate(value):
                    value[i] = str(ip_address(v))

        return record_list

    def record_create(self, domain, record_type, params):
        """
        Creates a record for a domain
        :param domain: Dict - a dictionary representing a domain
        :param record_type:  string - the record type (i.e. A, AAAA, etc)
        :param params: Dict - A dictionary holding the parameters that
        describe the record
        :return:
            Response - with the created record or an error message
        """
        # change ALIAS records to ANAME
        if record_type == 'ALIAS':
            record_type = 'ANAME'

        path = '/domains/{}/records/{}'.format(domain['id'], record_type)
        self._request('POST', path, data=params)

    def record_delete(self, zone_name, record_type, record_id):
        # change ALIAS records to ANAME
        if record_type == 'ALIAS':
            record_type = 'ANAME'

        zone_id = self.domains.get(zone_name, False)
        path = '/{}/records/{}/{}'.format(zone_id, record_type, record_id)
        self._request('DELETE', path)

    def pools(self, pool_type):
        """
        Retrieves all the pools for the account that have the specified
        pool type. Recall that in Constellix DNS, a pool is associated with
        an account, and can be used by the records in all the domains.
        :param pool_type: string - The pool type (i.e. A, AAAA, ANAME/CNAME)
        :return:
            JSON - list of pools for the specified type
        """
        path = '/pools/{}'.format(pool_type)
        return self._request('GET', path).json()

    def pool_with_name(self, pool_type, pool_name):   # pragma: no cover
        """
        Returns the first pool with the specified type and name
        :param pool_type: string - The pool type (i.e. A, AAAA, ANAME/CNAME)
        :param pool_name: string - The fully-qualified name of the pool
        :return:
            JSON | None - the json representation of the pool, or None if
            the pool wasn't found
        """
        pools = self.pools(pool_type)
        found = [pool for pool in pools if pool['name'] == pool_name]
        if len(found) == 0:
            return None

        return found[0]

    def pool_create(self, pool):     # pragma: no cover
        """
        Creates a weighted-round robin pool where the
        :param pool: Dict - {
            "name": string,
            "type": string,
            "numReturn": number,
            "minAvailableFailover": number,
            "ttl": number,
            "values": [{weight: number, value: string}]
        } Holds the fully-qualified pool name, the pool type, the
        number of IPs returned, and the minimum number of IPs available,
        the TTL, and a list of (value: IP, weight: number) pairs.
        :return:
            Dict - The pool that was just created
        """
        path = '/pools/{}'.format(pool.get('type'))
        return self._request('POST', path, data=[pool]).json()

    def pool_update(self, pool_id, update):     # pragma: no coverage
        """
        Updates the pool with the information specified in the update param
        :param pool_id: int - The ID of the pool
        :param update: Dict - Dictionary holding the parameters with which
        to update the pool
        :return:
            Dict - The updated pool
        """
        path = '/pools/{}/{}'.format(update.get('type'), pool_id)

        try:
            self._request('PUT', path, data=update).json()
        except ConstellixClientBadRequest as e:     # pragma: no cover
            if "no changes to save" not in e.message.lower():
                raise e
            return update

        update['id'] = pool_id
        return update


class ConstellixProvider(BaseProvider):
    """
    Constellix DNS provider
    constellix:
        class: octodns.provider.constellix.ConstellixProvider
        # Your Constellix api key (required)
        api_key: env/CONSTELLIX_API_KEY
        # Your Constellix secret key (required)
        secret_key: env/CONSTELLIX_SECRET_KEY
        # Amount of time to wait between requests to avoid
        # ratelimit (optional)
        ratelimit_delay: 0.0
    """
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = True
    SUPPORTS = {'A', 'AAAA', 'ALIAS', 'CAA', 'CNAME', 'MX', 'NS',
                'NAPTR', 'PTR', 'SPF', 'SRV', 'TXT'}

    def __init__(self, id, api_key, secret_key, ratelimit_delay=0.0,
                 *args, **kwargs):
        self.log = logging.getLogger('ConstellixProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, api_key=***, secret_key=***', id)
        super(ConstellixProvider, self).__init__(id, *args, **kwargs)
        self._client = ConstellixClient(api_key, secret_key, ratelimit_delay)
        self._zone_records = {}

    #
    # functions for interaction with the client
    #

    def zone_records(self, zone):
        """
        Retrieves the records for the specified domain
        :param zone: Zone - The zone for which to retrieve the records
        :return:
            list(Dict) - A list of records, where each record is represented
            by a dictionary
        """
        if zone.name not in self._zone_records:
            try:
                self._zone_records[zone.name] = \
                    self._client.records(zone.name)
            except ConstellixClientNotFound:
                return []

        return self._zone_records[zone.name]

    def populate(self, zone, target=False, lenient=False):
        """
        Loads all records the provider knows about for the provided zone
        :param zone: Zone - The domain for which to load the records
        :param target: boolean - True the populate call is being made to
        load the current state of the provider
        :param lenient: boolean - True the populate call may skip record
        validation and do a "best effort" load of data. That will allow
        through some common, but not best practices stuff that we otherwise
        would reject. E.g. no trailing . or missing escapes for ;.
        :return:
            boolean - True (loading current state) this method should return
            True if the zone exists or False if it does not.
        """
        self.log.debug(
            'populate: name=%s, target=%s, lenient=%s',
            zone.name, target, lenient
        )

        values = defaultdict(lambda: defaultdict(list))
        for record in self.zone_records(zone):
            _type = record['type']
            if _type not in self.SUPPORTS:
                self.log.warning(
                    'populate: skipping unsupported %s record',
                    _type
                )
                continue
            values[record['name']][record['type']].append(record)

        before = len(zone.records)
        for name, types in values.items():
            for _type, records in types.items():
                data_for = getattr(self, '_data_for_{}'.format(_type))
                record = Record.new(
                    zone, name, data_for(_type, records),
                    source=self, lenient=lenient
                )
                zone.add_record(record, lenient=lenient)

        exists = zone.name in self._zone_records
        self.log.info(
            'populate:   found %s records, exists=%s',
            len(zone.records) - before,
            exists
        )
        return exists

    def _deal_with_pools(self, record):
        """
        Attempts to create or overwrite the pool specified in the record
        under the dynamic property in the data. If a pool is defined, and
        if the pool is listed in the rules as a "pool", then this method
        determines whether the pool exists on Constellix DNS and should be
        overwritten, or, if it doesn't exist, attempts to create the pool.
        :param record: Dict - holding the new record
        :return:
            list - A list of the created or updated pools
        """
        # grab the data
        data = record.data
        # validate that the dynamic records are defined, and that
        # there are pools, and rules.
        if 'dynamic' not in data or 'pools' not in data.get('dynamic'):
            return None

        # these are the pool definitions, octodns validates that pools are
        # present
        pools = data.get('dynamic').get('pools')
        if pools is None or len(pools) == 0:    # pragma: no cover
            return None

        # these are the rules that hold the pools that are applied
        # to the record, and the geo info which we presently discard,
        # octodns validates that rules are there
        rules = data.get('dynamic').get('rules')
        if rules is None or len(rules) == 0:    # pragma: no cover
            return None

        # we treat an applied pool as the pools listed under the rules,
        # ignoring the geo (for now), there should only ever be on entry
        # with pool. If there is no entry with 'pool', then there are
        # no applied pools, and we are done. octodns validates that there
        # are is a pool with this name in the rules
        applied_pools = filter(lambda rule: 'pool' in rule.keys(), rules)
        if len(applied_pools) == 0:    # pragma: no cover
            return None

        applied_pool = applied_pools[0].get('pool')
        if applied_pool is None:    # pragma: no cover
            return None

        # we want only the pools that have (value, weight) pairs, because
        # those are the pools for the weighted round-robin. If the weight
        # isn't specified, octodns defaults the weight to 1
        pool = pools.get(applied_pool)
        if pool is None or \
                len(pool) == 0 or \
                pool.get('values') is None or \
                len(filter(
                    lambda value: 'value' in value and 'weight' in value,
                    pool.get('values')
                )) == 0:    # pragma: no cover
            return None

        # this should be a list of dicts with, each dict holding the
        # 'value' -> ip and a 'weight' -> number
        round_robin = pool.get('values')

        # create the name of the pool that will be create in constellix
        # dns. In constellix dns, a pool can be shared by all the domains
        # in the account. In octodns, a pool is specific to a record, so
        # we decorate the pool name with the domain and record names to
        # make it unique
        pool_name = ConstellixProvider._fully_qualified_pool_name(
            record.zone.name, record.name, record._type, applied_pool
        )

        # create or update the weighted pool
        return self._create_or_update_pool(
            fqpn=pool_name,
            pool_type=record._type,
            ttl=record.ttl,
            values=round_robin
        )

    @staticmethod
    def _fully_qualified_pool_name(domain_name,
                                   record_name,
                                   record_type,
                                   pool_name):
        """
        Creates a fully-qualified pool name if the form:
        "domain_name:record_name:pool_name". In Constellix DNS a pool is
        a resource that can be shared by records in all of the account's
        domains. In octodns, the pool belongs to the record. So we convert
        the octodns pool name to a fully qualified name so that it is
        unique in Constellix DNS.
        :param domain_name: string - The name of the domain to which the
        pool belongs
        :param record_name: string - The record name of to which the pool
        belongs (in octodns)
        :param record_type: string - The type of the record
        :param pool_name: string - The name of the pool as listed in the
        octodns config (yaml for the domain)
        :return:
            string - The fully-qualified pool name
        """
        return '{}:{}:{}:{}'.format(
            domain_name, record_name, record_type, pool_name
        )

    def _create_or_update_pool(self,
                               fqpn,
                               pool_type,
                               ttl,
                               values):    # pragma: no coverage
        """
        Creates a "Pool" for weighted round-robin (without Sonar checks), or
        if the pool already exists, updates it.
        :param fqpn: string - The fully qualified pool name
        :param pool_type: string - The pool type (i.e. A, AAAA, ANAME/CNAME)
        :param ttl: number - The time-to-live in seconds
        :param values: list - A list of objects holding the value, which
        is the IP address, and the weight for the round-robin.
        :return:
            JSON - a list holding the newly created pool
        """
        pool = {
            "name": fqpn,
            "type": pool_type,
            "numReturn": 1,
            "minAvailableFailover": 1,
            "ttl": ttl,
            "values": values
        }
        existing_pool = self._client.pool_with_name(pool_type, fqpn)

        # create pool if it doesn't already exist
        if existing_pool is None:
            return self._client.pool_create(pool)

        # pool exists, so overwrite it with the new values
        pool_id = existing_pool['id']
        updated_pool = self._client.pool_update(pool_id, pool)

        # enrich the updated pool with the existing pool ID
        updated_pool['id'] = pool_id
        return [updated_pool]

    def _apply_create(self, change, domain):
        """
        Calls the Constellix DNS API client to create the new record
        for the domain.
        :param change: Create - Holds the new record to add to the domain
        :param domain: Dict - Holds the key-value pairs representing the
        domain
        """
        new = change.new
        params_for = getattr(self, '_params_for_{}'.format(new._type))

        # deal with pools, if there are any specified
        new_pool = self._deal_with_pools(new)
        for params in params_for(new):
            if new_pool is not None:
                params['pools'] = [new_pool[0]['id']]
                params['recordOption'] = "pools"

            self._client.record_create(domain, new._type, params)

    def _apply_update(self, change, domain):
        """
        Updates the records specified in the change set by deleting and then
        recreating them
        :param change: Change - The octodns change that defines the actions
        :param domain: Dict - Holds the key-value pairs representing the
        domain
        """
        self._apply_delete(change, domain)
        self._apply_create(change, domain)

    def _apply_delete(self, change, domain):
        """
        Deletes the records specified in the change set
        :param change: Change - The change defining which records to delete
        :param domain: Dict - Holds the key-value pairs representing the
        domain
        """
        existing = change.existing
        zone = existing.zone
        for record in self.zone_records(zone):
            if existing.name == record['name'] and \
                    existing._type == record['type']:
                self._client.record_delete(
                    domain, record['type'],
                    record['id']
                )

    def _apply(self, plan):
        """
        Called by octodns (base.py) with the plan. The plan holds the
        changes required by this action: create, update, delete. The plan
        also holds the existing records. The plan is for a specific domain
        :param plan: Plan - The plan of actions and supporting data
        :return:
        """
        desired = plan.desired
        changes = plan.changes
        self.log.debug(
            '_apply: zone=%s, len(changes)=%d', desired.name,
            len(changes)
        )

        # retrieve the domain based on the name, and if it doesn't exist
        # then attempt to create the domain.
        try:
            domain = self._client.domain(desired.name)
        except ConstellixClientNotFound:
            self.log.debug('_apply:   no matching zone, creating domain')
            new_domains = self._client.domain_create(desired.name[:-1])
            domain = new_domains[0]

        # for each of the changes, call the appropriate _apply_x() function.
        # for example, when the change is 'Create', then call the
        # _apply_create(...) method for creating the records.
        for change in changes:
            class_name = change.__class__.__name__
            getattr(
                self,
                '_apply_{}'.format(class_name.lower())
            )(change, domain)

        # Clear out the cache if any
        self._zone_records.pop(desired.name, None)

    #
    # data retrieved from Constellix DNS API service
    #

    @staticmethod
    def _data_for_multiple(_type, records):
        record = records[0]
        return {
            'ttl': record['ttl'],
            'type': _type,
            'values': record['value']
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple

    @staticmethod
    def _data_for_CAA(_type, records):
        values = []
        record = records[0]
        for value in record['value']:
            values.append({
                'flags': value['flag'],
                'tag': value['tag'],
                'value': value['data']
                #'value': value
            })
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values
        }

    @staticmethod
    def _data_for_NS(_type, records):
        record = records[0]
        return {
            'ttl': record['ttl'],
            'type': _type,
            'values': [value['value'] for value in records['value']]
        }

    @staticmethod
    def _data_for_ALIAS(_type, records):
        record = records[0]
        enabled_fqdn = [r['value'] for r in record['value']
                        if r['disableFlag'] is False]
        if len(enabled_fqdn) > 0:     # pragma: no coverage
            fqdn = enabled_fqdn[0]
            return {
                'ttl': record['ttl'],
                'type': _type,
                'value': fqdn
            }
        else:   # pragma: no coverage
            return None

        _data_for_PTR = _data_for_ALIAS

    @staticmethod
    def _data_for_TXT(_type, records):
        txt_records = []
        for record in records:
            values = record['value']
            if isinstance(values, unicode):
                txt_records.append(values.replace(';', '\\;'))
            else:
                for value in values:
                    item = value['value'].replace(';', '\\;')
                    txt_records.append(item)

        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': txt_records
        }

    @staticmethod
    def _data_for_NAPTR(_type, records):
        values = []
        record = records[0]
        for value in record['value']:
            values.append({
                'flags': value['flags'],
                'order': value['order'],
                'service': value['service'],
                'preference': value['preference'],
                'regexp': value['regularExpression'],
                'replacement': value['replacement']
            })
        return {
            'ttl': record['ttl'],
            'type': _type,
            'values': values
        }

    _data_for_SPF = _data_for_TXT

    @staticmethod
    def _data_for_MX(_type, records):
        values = []
        record = records[0]
        for value in record['value']:
            values.append({
                'preference': value['level'],
                'exchange': value['value']
            })
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values
        }

    @staticmethod
    def _data_for_single(_type, records):
        record = records[0]
        return {
            'ttl': record['ttl'],
            'type': _type,
            'value': record['value']
        }

    _data_for_CNAME = _data_for_single

    @staticmethod
    def _data_for_SRV(_type, records):
        values = []
        record = records[0]
        for value in record['value']:
            values.append({
                'port': value['port'],
                'priority': value['priority'],
                'target': value['value'],
                'weight': value['weight']
            })
        return {
            'type': _type,
            'ttl': records[0]['ttl'],
            'values': values
        }

    #
    # parameters for sending requests to the Constellix DNS API service
    #

    @staticmethod
    def _params_for_multiple(record):
        yield {
            'name': record.name,
            'ttl': record.ttl,
            'roundRobin': [{'value': value} for value in record.values]
        }

    _params_for_A = _params_for_multiple
    _params_for_AAAA = _params_for_multiple

    # An A record with this name must exist in this domain for
    # this NS record to be valid. Need to handle checking if
    # there is an A record before creating NS
    _params_for_NS = _params_for_multiple

    @staticmethod
    def _params_for_single(record):
        yield {
            'name': record.name,
            'ttl': record.ttl,
            'host': record.value,
        }

    _params_for_CNAME = _params_for_single

    @staticmethod
    def _params_for_ALIAS(record):
        yield {
            'name': record.name,
            'ttl': record.ttl,
            'roundRobin': [{
                'value': record.value,
                'disableFlag': False
            }]
        }

    _params_for_PTR = _params_for_ALIAS

    @staticmethod
    def _params_for_MX(record):
        """
        Generator function for the MX record parameters
        :param record: MxRecord - The mail-exchange record
        :return:
            JSON: The parameters for the MX record
        """
        values = [
            {'value': value.exchange, 'level': value.preference}
            for value in record.values
        ]

        yield {
            'name': record.name,
            'ttl': record.ttl,
            'roundRobin': values
        }

    @staticmethod
    def _params_for_SRV(record):
        values = []
        for value in record.values:
            values.append({
                'value': value.target,
                'priority': value.priority,
                'weight': value.weight,
                'port': value.port
            })
        for _ in record.values:
            yield {
                'name': record.name,
                'ttl': record.ttl,
                'roundRobin': values
            }

    @staticmethod
    def _params_for_TXT(record):
        # Constellix does not want values escaped
        values = []
        for value in record.chunked_values:
            values.append({
                'value': value.replace('\\;', ';')
            })
        yield {
            'name': record.name,
            'ttl': record.ttl,
            'roundRobin': values
        }

    _params_for_SPF = _params_for_TXT

    @staticmethod
    def _params_for_CAA(record):
        values = []
        for value in record.values:
            values.append({
                'tag': value.tag,
                'data': value.value,
                'flag': value.flags,
            })
        yield {
            'name': record.name,
            'ttl': record.ttl,
            'roundRobin': values
        }

    @staticmethod
    def _params_for_NAPTR(record):
        values = []
        for value in record.values:
            values.append({
                'order': value.order,
                'preference': value.preference,
                'flags': value.flags,
                'service': value.service,
                'regularExpression': value.regexp,
                'replacement': value.replacement
            })
        yield {
            'name': record.name,
            'ttl': record.ttl,
            'roundRobin': values
        }
