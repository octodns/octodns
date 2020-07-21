#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict
from requests import Session
from time import sleep
import logging
import base64

from ..record import Record
from .base import BaseProvider


class EasyDNSClientException(Exception):
    pass


class EasyDNSClientBadRequest(EasyDNSClientException):

    def __init__(self):
        super(EasyDNSClientBadRequest, self).__init__('Bad request')


class EasyDNSClientNotFound(EasyDNSClientException):

    def __init__(self):
        super(EasyDNSClientNotFound, self).__init__('Not Found')


class EasyDNSClientUnauthorized(EasyDNSClientException):

    def __init__(self):
        super(EasyDNSClientUnauthorized, self).__init__('Unauthorized')


class EasyDNSClient(object):
    # EasyDNS Sandbox API
    SANDBOX = 'https://sandbox.rest.easydns.net'
    # EasyDNS Live API
    LIVE = 'https://rest.easydns.net'
    # Default Currency CAD
    default_currency = 'CAD'
    # Domain Portfolio
    domain_portfolio = 'myport'

    def __init__(self, token, api_key, currency, portfolio, sandbox):
        self.log = logging.getLogger('EasyDNSProvider[{}]'.format(id))
        self.token = token
        self.api_key = api_key
        self.default_currency = currency
        self.domain_portfolio = portfolio
        self.apienv = 'sandbox' if sandbox else 'live'
        auth_key = '{}:{}'.format(self.token, self.api_key)
        self.auth_key = base64.b64encode(auth_key.encode("utf-8"))
        self.base_path = self.SANDBOX if sandbox else self.LIVE
        sess = Session()
        sess.headers.update({'Authorization': 'Basic {}'
                             .format(self.auth_key)})
        sess.headers.update({'accept': 'application/json'})
        self._sess = sess

    def _request(self, method, path, params=None, data=None):
        url = '{}{}'.format(self.base_path, path)
        resp = self._sess.request(method, url, params=params, json=data)
        if resp.status_code == 400:
            self.log.debug('Response code 400, path=%s', path)
            if method == 'GET' and path[:8] == '/domain/':
                raise EasyDNSClientNotFound()
            raise EasyDNSClientBadRequest()
        if resp.status_code == 401:
            raise EasyDNSClientUnauthorized()
        if resp.status_code == 403 or resp.status_code == 404:
            raise EasyDNSClientNotFound()
        resp.raise_for_status()
        return resp

    def domain(self, name):
        path = '/domain/{}'.format(name)
        return self._request('GET', path).json()

    def domain_create(self, name):
        # EasyDNS allows for new domains to be created for the purpose of DNS
        # only, or with domain registration. This function creates a DNS only
        # record expectig the domain to be registered already
        path = '/domains/add/{}'.format(name)
        domain_data = {'service': 'dns',
                       'term': 1,
                       'dns_only': 1,
                       'portfolio': self.domain_portfolio,
                       'currency': self.default_currency}
        self._request('PUT', path, data=domain_data).json()

        # EasyDNS creates default records for MX, A and CNAME for new domains,
        # we need to delete those default record so we can sync with the source
        # records, first we'll sleep for a second before gathering new records
        # We also create default NS records, but they won't be deleted
        sleep(1)
        records = self.records(name, True)
        for record in records:
            if record['host'] in ('', 'www') \
               and record['type'] in ('A', 'MX', 'CNAME'):
                self.record_delete(name, record['id'])

    def records(self, zone_name, raw=False):
        if raw:
            path = '/zones/records/all/{}'.format(zone_name)
        else:
            path = '/zones/records/parsed/{}'.format(zone_name)

        ret = []
        resp = self._request('GET', path).json()
        ret += resp['data']

        for record in ret:
            # change any apex record to empty string
            if record['host'] == '@':
                record['host'] = ''

            # change any apex value to zone name
            if record['rdata'] == '@':
                record['rdata'] = '{}.'.format(zone_name)

        return ret

    def record_create(self, zone_name, params):
        path = '/zones/records/add/{}/{}'.format(zone_name, params['type'])
        # change empty name string to @, EasyDNS uses @ for apex record names
        params['host'] = params['name']
        if params['host'] == '':
            params['host'] = '@'
        self._request('PUT', path, data=params)

    def record_delete(self, zone_name, record_id):
        path = '/zones/records/{}/{}'.format(zone_name, record_id)
        self._request('DELETE', path)


class EasyDNSProvider(BaseProvider):
    '''
    EasyDNS provider using API v3

    easydns:
        class: octodns.provider.easydns.EasyDNSProvider
        # Your EasyDNS API token (required)
        token: foo
        # Your EasyDNS API Key (required)
        api_key: bar
        # Use SandBox or Live environment, optional, defaults to live
        sandbox: False
        # Currency to use for creating domains, default CAD
        default_currency: CAD
        # Domain Portfolio under which to create domains
        portfolio: myport
    '''
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set(('A', 'AAAA', 'CAA', 'CNAME', 'MX', 'NS', 'TXT',
                    'SRV', 'NAPTR'))

    def __init__(self, id, token, api_key, currency='CAD', portfolio='myport',
                 sandbox=False, *args, **kwargs):
        self.log = logging.getLogger('EasyDNSProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, token=***', id)
        super(EasyDNSProvider, self).__init__(id, *args, **kwargs)
        self._client = EasyDNSClient(token, api_key, currency, portfolio,
                                     sandbox)
        self._zone_records = {}

    def _data_for_multiple(self, _type, records):
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': [r['rdata'] for r in records]
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple

    def _data_for_CAA(self, _type, records):
        values = []
        for record in records:
            try:
                flags, tag, value = record['rdata'].split(' ', 2)
            except ValueError:
                continue
            values.append({
                'flags': flags,
                'tag': tag,
                'value': value,
            })
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values
        }

    def _data_for_NAPTR(self, _type, records):
        values = []
        for record in records:
            try:
                order, preference, flags, service, regexp, replacement = \
                    record['rdata'].split(' ', 5)
            except ValueError:
                continue
            values.append({
                'flags': flags[1:-1],
                'order': order,
                'preference': preference,
                'regexp': regexp[1:-1],
                'replacement': replacement,
                'service': service[1:-1],
            })
        return {
            'type': _type,
            'ttl': records[0]['ttl'],
            'values': values
        }

    def _data_for_CNAME(self, _type, records):
        record = records[0]
        return {
            'ttl': record['ttl'],
            'type': _type,
            'value': '{}'.format(record['rdata'])
        }

    def _data_for_MX(self, _type, records):
        values = []
        for record in records:
            values.append({
                'preference': record['prio'],
                'exchange': '{}'.format(record['rdata'])
            })
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values
        }

    def _data_for_NS(self, _type, records):
        values = []
        for record in records:
            data = '{}'.format(record['rdata'])
            values.append(data)
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values,
        }

    def _data_for_SRV(self, _type, records):
        values = []
        record = records[0]
        for record in records:
            try:
                priority, weight, port, target = record['rdata'].split(' ', 3)
            except ValueError:
                rdata = record['rdata'].split(' ', 3)
                priority = 0
                weight = 0
                port = 0
                target = ''
                if len(rdata) != 0 and rdata[0] != '':
                    priority = rdata[0]
                if len(rdata) >= 2:
                    weight = rdata[1]
                if len(rdata) >= 3:
                    port = rdata[2]
            values.append({
                'port': int(port),
                'priority': int(priority),
                'target': target,
                'weight': int(weight)
            })
        return {
            'type': _type,
            'ttl': records[0]['ttl'],
            'values': values
        }

    def _data_for_TXT(self, _type, records):
        values = ['"' + value['rdata'].replace(';', '\\;') +
                  '"' for value in records]
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values
        }

    def zone_records(self, zone):
        if zone.name not in self._zone_records:
            try:
                self._zone_records[zone.name] = \
                    self._client.records(zone.name[:-1])
            except EasyDNSClientNotFound:
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
            values[record['host']][record['type']].append(record)

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
        for value in record.values:
            yield {
                'rdata': value,
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type
            }

    _params_for_A = _params_for_multiple
    _params_for_AAAA = _params_for_multiple
    _params_for_NS = _params_for_multiple

    def _params_for_CAA(self, record):
        for value in record.values:
            yield {
                'rdata': "{} {} {}".format(value.flags, value.tag,
                                           value.value),
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type
            }

    def _params_for_NAPTR(self, record):
        for value in record.values:
            content = '{} {} "{}" "{}" "{}" {}'.format(value.order,
                                                       value.preference,
                                                       value.flags,
                                                       value.service,
                                                       value.regexp,
                                                       value.replacement)
            yield {
                'rdata': content,
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type
            }

    def _params_for_single(self, record):
        yield {
            'rdata': record.value,
            'name': record.name,
            'ttl': record.ttl,
            'type': record._type
        }

    _params_for_CNAME = _params_for_single

    def _params_for_MX(self, record):
        for value in record.values:
            yield {
                'rdata': value.exchange,
                'name': record.name,
                'prio': value.preference,
                'ttl': record.ttl,
                'type': record._type
            }

    def _params_for_SRV(self, record):
        for value in record.values:
            yield {
                'rdata': "{} {} {} {}".format(value.priority, value.port,
                                              value.weight, value.target),
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type,
            }

    def _params_for_TXT(self, record):
        for value in record.values:
            yield {
                'rdata': '"' + value.replace('\\;', ';') + '"',
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type
            }

    def _apply_Create(self, change):
        new = change.new
        params_for = getattr(self, '_params_for_{}'.format(new._type))
        for params in params_for(new):
            self._client.record_create(new.zone.name[:-1], params)

    def _apply_Update(self, change):
        self._apply_Delete(change)
        self._apply_Create(change)

    def _apply_Delete(self, change):
        existing = change.existing
        zone = existing.zone
        for record in self.zone_records(zone):
            self.log.debug('apply_Delete: zone=%s, type=%s, host=%s', zone,
                           record['type'], record['host'])
            if existing.name == record['host'] and \
               existing._type == record['type']:
                self._client.record_delete(zone.name[:-1], record['id'])

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        domain_name = desired.name[:-1]
        try:
            self._client.domain(domain_name)
        except EasyDNSClientNotFound:
            self.log.debug('_apply:   no matching zone, creating domain')
            self._client.domain_create(domain_name)

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name))(change)

        # Clear out the cache if any
        self._zone_records.pop(desired.name, None)
