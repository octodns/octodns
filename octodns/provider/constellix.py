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
        errors = resp.json()['errors']
        super(ConstellixClientBadRequest, self).__init__(
            '\n  - {}'.format('\n  - '.join(errors)))


class ConstellixClientUnauthorized(ConstellixClientException):

    def __init__(self):
        super(ConstellixClientUnauthorized, self).__init__('Unauthorized')


class ConstellixClientNotFound(ConstellixClientException):

    def __init__(self):
        super(ConstellixClientNotFound, self).__init__('Not Found')


class ConstellixClient(object):
    BASE = 'https://api.dns.constellix.com/v1/domains'

    def __init__(self, api_key, secret_key, ratelimit_delay=0.0):
        self.api_key = api_key
        self.secret_key = secret_key
        self.ratelimit_delay = ratelimit_delay
        self._sess = Session()
        self._sess.headers.update({'x-cnsdns-apiKey': self.api_key})
        self._domains = None

    def _current_time(self):
        return str(int(time.time() * 1000))

    def _hmac_hash(self, now):
        return hmac.new(self.secret_key.encode('utf-8'), now.encode('utf-8'),
                        digestmod=hashlib.sha1).digest()

    def _request(self, method, path, params=None, data=None):
        now = self._current_time()
        hmac_hash = self._hmac_hash(now)

        headers = {
            'x-cnsdns-hmac': b64encode(hmac_hash),
            'x-cnsdns-requestDate': now
        }

        url = '{}{}'.format(self.BASE, path)
        resp = self._sess.request(method, url, headers=headers,
                                  params=params, json=data)
        if resp.status_code == 400:
            raise ConstellixClientBadRequest(resp)
        if resp.status_code == 401:
            raise ConstellixClientUnauthorized()
        if resp.status_code == 404:
            raise ConstellixClientNotFound()
        resp.raise_for_status()
        time.sleep(self.ratelimit_delay)
        return resp

    @property
    def domains(self):
        if self._domains is None:
            zones = []

            resp = self._request('GET', '').json()
            zones += resp

            self._domains = {'{}.'.format(z['name']): z['id'] for z in zones}

        return self._domains

    def domain(self, name):
        zone_id = self.domains.get(name, False)
        if not zone_id:
            raise ConstellixClientNotFound()
        path = '/{}'.format(zone_id)
        return self._request('GET', path).json()

    def domain_create(self, name):
        resp = self._request('POST', '/', data={'names': [name]})
        # Add newly created zone to domain cache
        self._domains['{}.'.format(name)] = resp.json()[0]['id']

    def _absolutize_value(self, value, zone_name):
        if value == '':
            value = zone_name
        elif not value.endswith('.'):
            value = '{}.{}'.format(value, zone_name)

        return value

    def records(self, zone_name):
        zone_id = self.domains.get(zone_name, False)
        if not zone_id:
            raise ConstellixClientNotFound()
        path = '/{}/records'.format(zone_id)

        resp = self._request('GET', path).json()
        for record in resp:
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
                        v['value'] = self._absolutize_value(v['value'],
                                                            zone_name)

            # compress IPv6 addresses
            if record['type'] == 'AAAA':
                for i, v in enumerate(value):
                    value[i] = str(ip_address(v))

        return resp

    def record_create(self, zone_name, record_type, params):
        # change ALIAS records to ANAME
        if record_type == 'ALIAS':
            record_type = 'ANAME'

        zone_id = self.domains.get(zone_name, False)
        path = '/{}/records/{}'.format(zone_id, record_type)

        self._request('POST', path, data=params)

    def record_delete(self, zone_name, record_type, record_id):
        # change ALIAS records to ANAME
        if record_type == 'ALIAS':
            record_type = 'ANAME'

        zone_id = self.domains.get(zone_name, False)
        path = '/{}/records/{}/{}'.format(zone_id, record_type, record_id)
        self._request('DELETE', path)


class ConstellixProvider(BaseProvider):
    '''
    Constellix DNS provider

    constellix:
        class: octodns.provider.constellix.ConstellixProvider
        # Your Contellix api key (required)
        api_key: env/CONSTELLIX_API_KEY
        # Your Constellix secret key (required)
        secret_key: env/CONSTELLIX_SECRET_KEY
        # Amount of time to wait between requests to avoid
        # ratelimit (optional)
        ratelimit_delay: 0.0
    '''
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS_ROOT_NS = False
    SUPPORTS = set(('A', 'AAAA', 'ALIAS', 'CAA', 'CNAME', 'MX',
                    'NS', 'PTR', 'SPF', 'SRV', 'TXT'))

    def __init__(self, id, api_key, secret_key, ratelimit_delay=0.0,
                 *args, **kwargs):
        self.log = logging.getLogger('ConstellixProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, api_key=***, secret_key=***', id)
        super(ConstellixProvider, self).__init__(id, *args, **kwargs)
        self._client = ConstellixClient(api_key, secret_key, ratelimit_delay)
        self._zone_records = {}

    def _data_for_multiple(self, _type, records):
        record = records[0]
        return {
            'ttl': record['ttl'],
            'type': _type,
            'values': record['value']
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple

    def _data_for_CAA(self, _type, records):
        values = []
        record = records[0]
        for value in record['value']:
            values.append({
                'flags': value['flag'],
                'tag': value['tag'],
                'value': value['data']
            })
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values
        }

    def _data_for_NS(self, _type, records):
        record = records[0]
        return {
            'ttl': record['ttl'],
            'type': _type,
            'values': [value['value'] for value in record['value']]
        }

    def _data_for_ALIAS(self, _type, records):
        record = records[0]
        return {
            'ttl': record['ttl'],
            'type': _type,
            'value': record['value'][0]['value']
        }

    _data_for_PTR = _data_for_ALIAS

    def _data_for_TXT(self, _type, records):
        values = [value['value'].replace(';', '\\;')
                  for value in records[0]['value']]
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values
        }

    _data_for_SPF = _data_for_TXT

    def _data_for_MX(self, _type, records):
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

    def _data_for_single(self, _type, records):
        record = records[0]
        return {
            'ttl': record['ttl'],
            'type': _type,
            'value': record['value']
        }

    _data_for_CNAME = _data_for_single

    def _data_for_SRV(self, _type, records):
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

    def zone_records(self, zone):
        if zone.name not in self._zone_records:
            try:
                self._zone_records[zone.name] = \
                    self._client.records(zone.name)
            except ConstellixClientNotFound:
                return []

        return self._zone_records[zone.name]

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        values = defaultdict(lambda: defaultdict(list))
        for record in self.zone_records(zone):
            _type = record['type']
            if _type not in self.SUPPORTS:
                self.log.warning('populate: skipping unsupported %s record',
                                 _type)
                continue
            values[record['name']][record['type']].append(record)

        before = len(zone.records)
        for name, types in values.items():
            for _type, records in types.items():
                data_for = getattr(self, '_data_for_{}'.format(_type))
                record = Record.new(zone, name, data_for(_type, records),
                                    source=self, lenient=lenient)
                zone.add_record(record, lenient=lenient)

        exists = zone.name in self._zone_records
        self.log.info('populate:   found %s records, exists=%s',
                      len(zone.records) - before, exists)
        return exists

    def _params_for_multiple(self, record):
        yield {
            'name': record.name,
            'ttl': record.ttl,
            'roundRobin': [{
                'value': value
            } for value in record.values]
        }

    _params_for_A = _params_for_multiple
    _params_for_AAAA = _params_for_multiple

    # An A record with this name must exist in this domain for
    # this NS record to be valid. Need to handle checking if
    # there is an A record before creating NS
    _params_for_NS = _params_for_multiple

    def _params_for_single(self, record):
        yield {
            'name': record.name,
            'ttl': record.ttl,
            'host': record.value,
        }

    _params_for_CNAME = _params_for_single

    def _params_for_ALIAS(self, record):
        yield {
            'name': record.name,
            'ttl': record.ttl,
            'roundRobin': [{
                'value': record.value,
                'disableFlag': False
            }]
        }

    _params_for_PTR = _params_for_ALIAS

    def _params_for_MX(self, record):
        values = []
        for value in record.values:
            values.append({
                'value': value.exchange,
                'level': value.preference
            })
        yield {
            'value': value.exchange,
            'name': record.name,
            'ttl': record.ttl,
            'roundRobin': values
        }

    def _params_for_SRV(self, record):
        values = []
        for value in record.values:
            values.append({
                'value': value.target,
                'priority': value.priority,
                'weight': value.weight,
                'port': value.port
            })
        for value in record.values:
            yield {
                'name': record.name,
                'ttl': record.ttl,
                'roundRobin': values
            }

    def _params_for_TXT(self, record):
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

    def _params_for_CAA(self, record):
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

    def _apply_Create(self, change):
        new = change.new
        params_for = getattr(self, '_params_for_{}'.format(new._type))
        for params in params_for(new):
            self._client.record_create(new.zone.name, new._type, params)

    def _apply_Update(self, change):
        self._apply_Delete(change)
        self._apply_Create(change)

    def _apply_Delete(self, change):
        existing = change.existing
        zone = existing.zone
        for record in self.zone_records(zone):
            if existing.name == record['name'] and \
               existing._type == record['type']:
                self._client.record_delete(zone.name, record['type'],
                                           record['id'])

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        try:
            self._client.domain(desired.name)
        except ConstellixClientNotFound:
            self.log.debug('_apply:   no matching zone, creating domain')
            self._client.domain_create(desired.name[:-1])

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name))(change)

        # Clear out the cache if any
        self._zone_records.pop(desired.name, None)
