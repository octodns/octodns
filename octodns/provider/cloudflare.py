#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict
from logging import getLogger
from requests import Session

from ..record import Record, Update
from .base import BaseProvider


class CloudflareAuthenticationError(Exception):

    def __init__(self, data):
        try:
            message = data['errors'][0]['message']
        except (IndexError, KeyError):
            message = 'Authentication error'
        super(CloudflareAuthenticationError, self).__init__(message)


class CloudflareProvider(BaseProvider):
    '''
    Cloudflare DNS provider

    cloudflare:
        class: octodns.provider.cloudflare.CloudflareProvider
        # Your Cloudflare account email address (required)
        email: dns-manager@example.com
        # The api key (required)
        token: foo
    '''
    SUPPORTS_GEO = False
    # TODO: support SRV
    SUPPORTS = set(('A', 'AAAA', 'CNAME', 'MX', 'NS', 'SPF', 'TXT'))

    MIN_TTL = 120
    TIMEOUT = 15

    def __init__(self, id, email, token, *args, **kwargs):
        self.log = getLogger('CloudflareProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, email=%s, token=***', id, email)
        super(CloudflareProvider, self).__init__(id, *args, **kwargs)

        sess = Session()
        sess.headers.update({
            'X-Auth-Email': email,
            'X-Auth-Key': token,
        })
        self._sess = sess

        self._zones = None
        self._zone_records = {}

    def _request(self, method, path, params=None, data=None):
        self.log.debug('_request: method=%s, path=%s', method, path)

        url = 'https://api.cloudflare.com/client/v4{}'.format(path)
        resp = self._sess.request(method, url, params=params, json=data,
                                  timeout=self.TIMEOUT)
        self.log.debug('_request:   status=%d', resp.status_code)
        if resp.status_code == 403:
            raise CloudflareAuthenticationError(resp.json())
        resp.raise_for_status()
        return resp.json()

    @property
    def zones(self):
        if self._zones is None:
            page = 1
            zones = []
            while page:
                resp = self._request('GET', '/zones', params={'page': page})
                zones += resp['result']
                info = resp['result_info']
                if info['count'] > 0 and info['count'] == info['per_page']:
                    page += 1
                else:
                    page = None

            self._zones = {'{}.'.format(z['name']): z['id'] for z in zones}

        return self._zones

    def _data_for_multiple(self, _type, records):
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': [r['content'] for r in records],
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple
    _data_for_SPF = _data_for_multiple

    def _data_for_TXT(self, _type, records):
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': [r['content'].replace(';', '\;') for r in records],
        }

    def _data_for_CNAME(self, _type, records):
        only = records[0]
        return {
            'ttl': only['ttl'],
            'type': _type,
            'value': '{}.'.format(only['content'])
        }

    def _data_for_MX(self, _type, records):
        values = []
        for r in records:
            values.append({
                'preference': r['priority'],
                'exchange': '{}.'.format(r['content']),
            })
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values,
        }

    def _data_for_NS(self, _type, records):
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': ['{}.'.format(r['content']) for r in records],
        }

    def zone_records(self, zone):
        if zone.name not in self._zone_records:
            zone_id = self.zones.get(zone.name, False)
            if not zone_id:
                return []

            records = []
            path = '/zones/{}/dns_records'.format(zone_id)
            page = 1
            while page:
                resp = self._request('GET', path, params={'page': page})
                records += resp['result']
                info = resp['result_info']
                if info['count'] > 0 and info['count'] == info['per_page']:
                    page += 1
                else:
                    page = None

            self._zone_records[zone.name] = records

        return self._zone_records[zone.name]

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

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

    def _include_change(self, change):
        if isinstance(change, Update):
            existing = change.existing.data
            new = change.new.data
            new['ttl'] = max(120, new['ttl'])
            if new == existing:
                return False
        return True

    def _contents_for_multiple(self, record):
        for value in record.values:
            yield {'content': value}

    _contents_for_A = _contents_for_multiple
    _contents_for_AAAA = _contents_for_multiple
    _contents_for_NS = _contents_for_multiple
    _contents_for_SPF = _contents_for_multiple

    def _contents_for_TXT(self, record):
        for value in record.values:
            yield {'content': value.replace('\;', ';')}

    def _contents_for_CNAME(self, record):
        yield {'content': record.value}

    def _contents_for_MX(self, record):
        for value in record.values:
            yield {
                'priority': value.preference,
                'content': value.exchange
            }

    def _apply_Create(self, change):
        new = change.new
        zone_id = self.zones[new.zone.name]
        contents_for = getattr(self, '_contents_for_{}'.format(new._type))
        path = '/zones/{}/dns_records'.format(zone_id)
        name = new.fqdn[:-1]
        for content in contents_for(change.new):
            content.update({
                'name': name,
                'type': new._type,
                # Cloudflare has a min ttl of 120s
                'ttl': max(self.MIN_TTL, new.ttl),
            })
            self._request('POST', path, data=content)

    def _apply_Update(self, change):
        # Create the new and delete the old
        self._apply_Create(change)
        self._apply_Delete(change)

    def _apply_Delete(self, change):
        existing = change.existing
        existing_name = existing.fqdn[:-1]
        for record in self.zone_records(existing.zone):
            if existing_name == record['name'] and \
               existing._type == record['type']:
                path = '/zones/{}/dns_records/{}'.format(record['zone_id'],
                                                         record['id'])
                self._request('DELETE', path)

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        name = desired.name
        if name not in self.zones:
            self.log.debug('_apply:   no matching zone, creating')
            data = {
                'name': name[:-1],
                'jump_start': False,
            }
            resp = self._request('POST', '/zones', data=data)
            zone_id = resp['result']['id']
            self.zones[name] = zone_id
            self._zone_records[name] = {}

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name))(change)

        # clear the cache
        self._zone_records.pop(name, None)
