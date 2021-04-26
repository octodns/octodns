#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict
from requests import Session
import logging

from ..record import Record
from .base import BaseProvider


class HetznerClientException(Exception):
    pass


class HetznerClientNotFound(HetznerClientException):

    def __init__(self):
        super(HetznerClientNotFound, self).__init__('Not Found')


class HetznerClientUnauthorized(HetznerClientException):

    def __init__(self):
        super(HetznerClientUnauthorized, self).__init__('Unauthorized')


class HetznerClient(object):
    '''
    Hetzner DNS Public API v1 client class.

    Zone and Record resources are (almost) fully supported, even if unnecessary
    to future-proof this client. Bulk Record create/update is not supported.

    No support for Primary Servers.
    '''

    BASE_URL = 'https://dns.hetzner.com/api/v1'

    def __init__(self, token):
        session = Session()
        session.headers.update({'Auth-API-Token': token})
        self._session = session

    def _do_raw(self, method, path, params=None, data=None):
        url = self.BASE_URL + path
        response = self._session.request(method, url, params=params, json=data)
        if response.status_code == 401:
            raise HetznerClientUnauthorized()
        if response.status_code == 404:
            raise HetznerClientNotFound()
        response.raise_for_status()
        return response

    def _do(self, method, path, params=None, data=None):
        return self._do_raw(method, path, params, data).json()

    def _do_with_pagination(self, method, path, key, params=None, data=None,
                            per_page=100):
        pagination_params = {'page': 1, 'per_page': per_page}
        if params is not None:
            params = {**params, **pagination_params}
        else:
            params = pagination_params

        items = []
        while True:
            response = self._do(method, path, params, data)
            items += response[key]
            if response['meta']['pagination']['page'] >= \
               response['meta']['pagination']['last_page']:
                break
            params['page'] += 1
        return items

    def zones_get(self, name=None, search_name=None):
        params = {'name': name, 'search_name': search_name}
        return self._do_with_pagination('GET', '/zones', 'zones',
                                        params=params)

    def zone_get(self, zone_id):
        return self._do('GET', '/zones/' + zone_id)['zone']

    def zone_create(self, name, ttl=None):
        data = {'name': name, 'ttl': ttl}
        return self._do('POST', '/zones', data=data)['zone']

    def zone_update(self, zone_id, name, ttl=None):
        data = {'name': name, 'ttl': ttl}
        return self._do('PUT', '/zones/' + zone_id, data=data)['zone']

    def zone_delete(self, zone_id):
        return self._do('DELETE', '/zones/' + zone_id)

    def _replace_at(self, record):
        record['name'] = '' if record['name'] == '@' else record['name']
        return record

    def zone_records_get(self, zone_id):
        params = {'zone_id': zone_id}
        # No need to handle pagination as it returns all records by default.
        return [
            self._replace_at(record)
            for record in self._do('GET', '/records', params=params)['records']
        ]

    def zone_record_get(self, record_id):
        record = self._do('GET', '/records/' + record_id)['record']
        return self._replace_at(record)

    def zone_record_create(self, zone_id, name, _type, value, ttl=None):
        data = {'name': name or '@', 'ttl': ttl, 'type': _type, 'value': value,
                'zone_id': zone_id}
        record = self._do('POST', '/records', data=data)['record']
        return self._replace_at(record)

    def zone_record_update(self, zone_id, record_id, name, _type, value,
                           ttl=None):
        data = {'name': name or '@', 'ttl': ttl, 'type': _type, 'value': value,
                'zone_id': zone_id}
        record = self._do('PUT', '/records/' + record_id, data=data)['record']
        return self._replace_at(record)

    def zone_record_delete(self, zone_id, record_id):
        return self._do('DELETE', '/records/' + record_id)


class HetznerProvider(BaseProvider):
    '''
    Hetzner DNS provider using API v1

    hetzner:
        class: octodns.provider.hetzner.HetznerProvider
        # Your Hetzner API token (required)
        token: foo
    '''
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set(('A', 'AAAA', 'CAA', 'CNAME', 'MX', 'NS', 'SRV', 'TXT'))

    def __init__(self, id, token, *args, **kwargs):
        self.log = logging.getLogger('HetznerProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, token=***', id)
        super(HetznerProvider, self).__init__(id, *args, **kwargs)
        self._client = HetznerClient(token)

        self._zone_records = {}
        self._zone_metadata = {}

    def _append_dot(self, value):
        if value == '@' or value[-1] == '.':
            return value
        return '{}.'.format(value)

    def _record_ttl(self, record):
        if 'ttl' in record:
            return record['ttl']
        return self._zone_metadata[record['zone_id']]['ttl']

    def _data_for_multiple(self, _type, records):
        values = [record['value'].replace(';', '\\;') for record in records]
        return {
            'ttl': self._record_ttl(records[0]),
            'type': _type,
            'values': values
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple

    def _data_for_CAA(self, _type, records):
        values = []
        for record in records:
            value_without_spaces = record['value'].replace(' ', '')
            flags = value_without_spaces[0]
            tag = value_without_spaces[1:].split('"')[0]
            value = record['value'].split('"')[1]
            values.append({
                'flags': int(flags),
                'tag': tag,
                'value': value,
            })
        return {
            'ttl': self._record_ttl(records[0]),
            'type': _type,
            'values': values
        }

    def _data_for_CNAME(self, _type, records):
        record = records[0]
        return {
            'ttl': self._record_ttl(record),
            'type': _type,
            'value': self._append_dot(record['value'])
        }

    def _data_for_MX(self, _type, records):
        values = []
        for record in records:
            value_stripped_split = record['value'].strip().split(' ')
            preference = value_stripped_split[0]
            exchange = value_stripped_split[-1]
            values.append({
                'preference': int(preference),
                'exchange': self._append_dot(exchange)
            })
        return {
            'ttl': self._record_ttl(records[0]),
            'type': _type,
            'values': values
        }

    def _data_for_NS(self, _type, records):
        values = []
        for record in records:
            values.append(self._append_dot(record['value']))
        return {
            'ttl': self._record_ttl(records[0]),
            'type': _type,
            'values': values,
        }

    def _data_for_SRV(self, _type, records):
        values = []
        for record in records:
            value_stripped = record['value'].strip()
            priority = value_stripped.split(' ')[0]
            weight = value_stripped[len(priority):].strip().split(' ')[0]
            target = value_stripped.split(' ')[-1]
            port = value_stripped[:-len(target)].strip().split(' ')[-1]
            values.append({
                'port': int(port),
                'priority': int(priority),
                'target': self._append_dot(target),
                'weight': int(weight)
            })
        return {
            'ttl': self._record_ttl(records[0]),
            'type': _type,
            'values': values
        }

    _data_for_TXT = _data_for_multiple

    def zone_records(self, zone):
        if zone.name not in self._zone_records:
            try:
                zone_metadata = self._client.zones_get(name=zone.name[:-1])[0]
                self._zone_metadata[zone_metadata['id']] = zone_metadata
                self._zone_records[zone.name] = \
                    self._client.zone_records_get(zone_metadata['id'])
            except HetznerClientNotFound:
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
        for value in record.values:
            yield {
                'value': value.replace('\\;', ';'),
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type
            }

    _params_for_A = _params_for_multiple
    _params_for_AAAA = _params_for_multiple

    def _params_for_CAA(self, record):
        for value in record.values:
            data = '{} {} "{}"'.format(value.flags, value.tag, value.value)
            yield {
                'value': data,
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type
            }

    def _params_for_single(self, record):
        yield {
            'value': record.value,
            'name': record.name,
            'ttl': record.ttl,
            'type': record._type
        }

    _params_for_CNAME = _params_for_single

    def _params_for_MX(self, record):
        for value in record.values:
            data = '{} {}'.format(value.preference, value.exchange)
            yield {
                'value': data,
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type
            }

    _params_for_NS = _params_for_multiple

    def _params_for_SRV(self, record):
        for value in record.values:
            data = '{} {} {} {}'.format(value.priority, value.weight,
                                        value.port, value.target)
            yield {
                'value': data,
                'name': record.name,
                'ttl': record.ttl,
                'type': record._type
            }

    _params_for_TXT = _params_for_multiple

    def _apply_Create(self, zone_id, change):
        new = change.new
        params_for = getattr(self, '_params_for_{}'.format(new._type))
        for params in params_for(new):
            self._client.zone_record_create(zone_id, params['name'],
                                            params['type'], params['value'],
                                            params['ttl'])

    def _apply_Update(self, zone_id, change):
        # It's way simpler to delete-then-recreate than to update
        self._apply_Delete(zone_id, change)
        self._apply_Create(zone_id, change)

    def _apply_Delete(self, zone_id, change):
        existing = change.existing
        zone = existing.zone
        for record in self.zone_records(zone):
            if existing.name == record['name'] and \
               existing._type == record['type']:
                self._client.zone_record_delete(zone_id, record['id'])

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        zone_name = desired.name[:-1]
        try:
            zone_id = self._client.zones_get(name=zone_name)[0]['id']
        except HetznerClientNotFound:
            self.log.debug('_apply:   no matching zone, creating domain')
            zone_id = self._client.zone_create(zone_name)['id']

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name))(zone_id, change)

        # Clear out the cache if any
        self._zone_records.pop(desired.name, None)
