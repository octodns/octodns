#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict

from logging import getLogger

from requests import Session

from ..record import Record
from .base import BaseProvider


class SelectelAuthenticationRequired(Exception):
    def __init__(self, msg):
        Exception.__init__(self,
                           'Authorization failed. Invalid or empty token.')


class SelectelProvider(BaseProvider):
    SUPPORTS_GEO = False

    SUPPORTS = set(('A', 'AAAA', 'CNAME', 'MX', 'NS', 'TXT', 'SRV'))

    MIN_TTL = 60
    MAX_TTL = 604800

    API_URL = 'https://api.selectel.ru/domains/v1'

    def __init__(self, id, token, *args, **kwargs):
        self.log = getLogger('SelectelProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s', id)
        super(SelectelProvider, self).__init__(id, *args, **kwargs)

        self._sess = Session()
        self._sess.headers.update({
            'X-Token': token,
            'Content-Type': 'application/json',
        })
        self._zone_records = {}
        self._domain_list = self.domain_list()

    def _request(self, method, path, params=None, data=None):
        self.log.debug('_request: method=%s, path=%s', method, path)

        url = '{}{}'.format(self.API_URL, path)
        resp = self._sess.request(method, url, params=params, json=data)
        self.log.debug('_request: status=%s', resp.status_code)
        if resp.status_code == 401:
            raise SelectelAuthenticationRequired(resp.text)
        elif resp.status_code == 404:
            return {}
        resp.raise_for_status()
        if method == 'DELETE':
            return {}
        if resp.json():
            return resp.json()

        self.log.debug('_request: empty response')
        return {}

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        zone_name = desired.name[:-1]

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name).lower())(zone_name,
                                                                  change)

    def _apply_create(self, zone_name, change):
        new = change.new
        params_for = getattr(self, '_params_for_{}'.format(new._type))
        for params in params_for(new):
            self.create_record(zone_name, params)

    def _apply_update(self, zone_name, change):
        self._apply_delete(zone_name, change)
        self._apply_create(zone_name, change)

    def _apply_delete(self, zone_name, change):
        existing = change.existing
        self.delete_record(zone_name, existing._type, existing.name)

    def _params_for_multiple(self, record):
        for value in record.values:
            yield {
                'content': value,
                'name': record.fqdn,
                'ttl': max(self.MIN_TTL, record.ttl),
                'type': record._type,
            }

    def _params_for_single(self, record):
        yield {
            'content': record.value,
            'name': record.fqdn,
            'ttl': max(self.MIN_TTL, record.ttl),
            'type': record._type
        }

    def _params_for_MX(self, record):
        for value in record.values:
            yield {
                'content': value.exchange,
                'name': record.fqdn,
                'ttl': max(self.MIN_TTL, record.ttl),
                'type': record._type,
                'priority': value.preference
            }

    def _params_for_SRV(self, record):
        for value in record.values:
            yield {
                'name': record.fqdn,
                'target': value.target,
                'ttl': max(self.MIN_TTL, record.ttl),
                'type': record._type,
                'port': value.port,
                'weight': value.weight,
                'priority': value.priority
            }

    _params_for_A = _params_for_multiple
    _params_for_AAAA = _params_for_multiple
    _params_for_NS = _params_for_multiple
    _params_for_TXT = _params_for_multiple

    _params_for_CNAME = _params_for_single

    def _data_for_A(self, _type, records):
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': [r['content'] for r in records],
        }

    _data_for_AAAA = _data_for_A

    def _data_for_NS(self, _type, records):
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': ['{}.'.format(r['content']) for r in records],
        }

    def _data_for_MX(self, _type, records):
        values = []
        for record in records:
            values.append({
                'preference': record['priority'],
                'exchange': '{}.'.format(record['content']),
            })
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values,
        }

    def _data_for_CNAME(self, _type, records):
        only = records[0]
        return {
            'ttl': only['ttl'],
            'type': _type,
            'value': '{}.'.format(only['content'])
        }

    def _data_for_TXT(self, _type, records):
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': [r['content'] for r in records],
        }

    def _data_for_SRV(self, _type, records):
        values = []
        for record in records:
            values.append({
                'priority': record['priority'],
                'weight': record['weight'],
                'port': record['port'],
                'target': '{}.'.format(record['target']),
            })

        return {
            'type': _type,
            'ttl': records[0]['ttl'],
            'values': values,
        }

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s',
                       zone.name, target, lenient)
        before = len(zone.records)
        records = self.zone_records(zone)
        if records:
            values = defaultdict(lambda: defaultdict(list))
            for record in records:
                name = zone.hostname_from_fqdn(record['name'])
                _type = record['type']
                if _type in self.SUPPORTS:
                    values[name][record['type']].append(record)
            for name, types in values.items():
                for _type, records in types.items():
                    data_for = getattr(self, '_data_for_{}'.format(_type))
                    data = data_for(_type, records)
                    record = Record.new(zone, name, data, source=self,
                                        lenient=lenient)
                    zone.add_record(record)
        self.log.info('populate:   found %s records',
                      len(zone.records) - before)

    def domain_list(self):
        path = '/'

        resp = self._request('GET', path)
        domain_dict = {}

        for domain in resp:
            domain_dict[domain['name']] = domain

        return domain_dict

    def zone_records(self, zone):
        path = '/{}/records/'.format(zone.name[:-1])
        resp = self._request('GET', path)

        self._zone_records[zone.name] = resp

        return self._zone_records[zone.name]

    def create_domain(self, name, zone=""):
        path = '/'

        data = {
            'name': name,
            'bind_zone': zone,
        }

        resp = self._request('POST', path, data=data)
        self._domain_list[name] = resp
        return resp

    def create_record(self, zone_name, data):
        self.log.debug('Create record. Zone: %s, data %s', zone_name, data)
        if zone_name in self._domain_list.keys():
            domain_id = self._domain_list[zone_name]['id']
        else:
            domain_id = self.create_domain(zone_name)['id']

        path = '/{}/records/'.format(domain_id)
        return self._request('POST', path, data=data)

    def delete_record(self, domain, _type, zone):
        self.log.debug('Delete record. Domain: %s, Type: %s', domain, _type)

        domain_id = self._domain_list[domain]['id']
        path = '/{}/records/'.format(domain_id)

        records = self._request('GET', path)
        for record in records:
            full_domain = domain
            if zone:
                full_domain = '{}.{}'.format(zone, domain)

            if record['type'] == _type and record['name'] == full_domain:
                path = '/{}/records/{}'.format(domain_id, record['id'])
                return self._request('DELETE', path)

        self.log.debug('Delete record failed (Record not found)')
