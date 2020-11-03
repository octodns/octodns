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


class GandiClientException(Exception):
    pass


class GandiClientBadRequest(GandiClientException):

    def __init__(self, r):
        super(GandiClientBadRequest, self).__init__(r.text)


class GandiClientUnauthorized(GandiClientException):

    def __init__(self, r):
        super(GandiClientUnauthorized, self).__init__(r.text)


class GandiClientForbidden(GandiClientException):

    def __init__(self, r):
        super(GandiClientForbidden, self).__init__(r.text)


class GandiClientNotFound(GandiClientException):

    def __init__(self, r):
        super(GandiClientNotFound, self).__init__(r.text)


class GandiClientUnknownDomainName(GandiClientException):

    def __init__(self, msg):
        super(GandiClientUnknownDomainName, self).__init__(msg)


class GandiClient(object):

    def __init__(self, token):
        session = Session()
        session.headers.update({'Authorization': 'Apikey {}'.format(token)})
        self._session = session
        self.endpoint = 'https://api.gandi.net/v5'

    def _request(self, method, path, params={}, data=None):
        url = '{}{}'.format(self.endpoint, path)
        r = self._session.request(method, url, params=params, json=data)
        if r.status_code == 400:
            raise GandiClientBadRequest(r)
        if r.status_code == 401:
            raise GandiClientUnauthorized(r)
        elif r.status_code == 403:
            raise GandiClientForbidden(r)
        elif r.status_code == 404:
            raise GandiClientNotFound(r)
        r.raise_for_status()
        return r

    def zone(self, zone_name):
        return self._request('GET', '/livedns/domains/{}'
                                    .format(zone_name)).json()

    def zone_create(self, zone_name):
        return self._request('POST', '/livedns/domains', data={
            'fqdn': zone_name,
            'zone': {}
        }).json()

    def zone_records(self, zone_name):
        records = self._request('GET', '/livedns/domains/{}/records'
                                .format(zone_name)).json()

        for record in records:
            if record['rrset_name'] == '@':
                record['rrset_name'] = ''

            # Change relative targets to absolute ones.
            if record['rrset_type'] in ['ALIAS', 'CNAME', 'DNAME', 'MX',
                                        'NS', 'SRV']:
                for i, value in enumerate(record['rrset_values']):
                    if not value.endswith('.'):
                        record['rrset_values'][i] = '{}.{}.'.format(
                            value, zone_name)

        return records

    def record_create(self, zone_name, data):
        self._request('POST', '/livedns/domains/{}/records'.format(zone_name),
                      data=data)

    def record_delete(self, zone_name, record_name, record_type):
        self._request('DELETE', '/livedns/domains/{}/records/{}/{}'
                      .format(zone_name, record_name, record_type))


class GandiProvider(BaseProvider):
    '''
    Gandi provider using API v5.

    gandi:
        class: octodns.provider.gandi.GandiProvider
        # Your API key (required)
        token: XXXXXXXXXXXX
    '''

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set((['A', 'AAAA', 'ALIAS', 'CAA', 'CNAME', 'DNAME',
                     'MX', 'NS', 'PTR', 'SPF', 'SRV', 'SSHFP', 'TXT']))

    def __init__(self, id, token, *args, **kwargs):
        self.log = logging.getLogger('GandiProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, token=***', id)
        super(GandiProvider, self).__init__(id, *args, **kwargs)
        self._client = GandiClient(token)

        self._zone_records = {}

    def _data_for_multiple(self, _type, records):
        return {
            'ttl': records[0]['rrset_ttl'],
            'type': _type,
            'values': [v.replace(';', '\\;') for v in
                       records[0]['rrset_values']] if _type == 'TXT' else
            records[0]['rrset_values']
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple
    _data_for_TXT = _data_for_multiple
    _data_for_SPF = _data_for_multiple
    _data_for_NS = _data_for_multiple

    def _data_for_CAA(self, _type, records):
        values = []
        for record in records[0]['rrset_values']:
            flags, tag, value = record.split(' ')
            values.append({
                'flags': flags,
                'tag': tag,
                # Remove quotes around value.
                'value': value[1:-1],
            })

        return {
            'ttl': records[0]['rrset_ttl'],
            'type': _type,
            'values': values
        }

    def _data_for_single(self, _type, records):
        return {
            'ttl': records[0]['rrset_ttl'],
            'type': _type,
            'value': records[0]['rrset_values'][0]
        }

    _data_for_ALIAS = _data_for_single
    _data_for_CNAME = _data_for_single
    _data_for_DNAME = _data_for_single
    _data_for_PTR = _data_for_single

    def _data_for_MX(self, _type, records):
        values = []
        for record in records[0]['rrset_values']:
            priority, server = record.split(' ')
            values.append({
                'preference': priority,
                'exchange': server
            })

        return {
            'ttl': records[0]['rrset_ttl'],
            'type': _type,
            'values': values
        }

    def _data_for_SRV(self, _type, records):
        values = []
        for record in records[0]['rrset_values']:
            priority, weight, port, target = record.split(' ', 3)
            values.append({
                'priority': priority,
                'weight': weight,
                'port': port,
                'target': target
            })

        return {
            'ttl': records[0]['rrset_ttl'],
            'type': _type,
            'values': values
        }

    def _data_for_SSHFP(self, _type, records):
        values = []
        for record in records[0]['rrset_values']:
            algorithm, fingerprint_type, fingerprint = record.split(' ', 2)
            values.append({
                'algorithm': algorithm,
                'fingerprint': fingerprint,
                'fingerprint_type': fingerprint_type
            })

        return {
            'ttl': records[0]['rrset_ttl'],
            'type': _type,
            'values': values
        }

    def zone_records(self, zone):
        if zone.name not in self._zone_records:
            try:
                self._zone_records[zone.name] = \
                    self._client.zone_records(zone.name[:-1])
            except GandiClientNotFound:
                return []

        return self._zone_records[zone.name]

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        values = defaultdict(lambda: defaultdict(list))
        for record in self.zone_records(zone):
            _type = record['rrset_type']
            if _type not in self.SUPPORTS:
                continue
            values[record['rrset_name']][record['rrset_type']].append(record)

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

    def _record_name(self, name):
        return name if name else '@'

    def _params_for_multiple(self, record):
        return {
            'rrset_name': self._record_name(record.name),
            'rrset_ttl': record.ttl,
            'rrset_type': record._type,
            'rrset_values': [v.replace('\\;', ';') for v in
                             record.values] if record._type == 'TXT'
            else record.values
        }

    _params_for_A = _params_for_multiple
    _params_for_AAAA = _params_for_multiple
    _params_for_NS = _params_for_multiple
    _params_for_TXT = _params_for_multiple
    _params_for_SPF = _params_for_multiple

    def _params_for_CAA(self, record):
        return {
            'rrset_name': self._record_name(record.name),
            'rrset_ttl': record.ttl,
            'rrset_type': record._type,
            'rrset_values': ['{} {} "{}"'.format(v.flags, v.tag, v.value)
                             for v in record.values]
        }

    def _params_for_single(self, record):
        return {
            'rrset_name': self._record_name(record.name),
            'rrset_ttl': record.ttl,
            'rrset_type': record._type,
            'rrset_values': [record.value]
        }

    _params_for_ALIAS = _params_for_single
    _params_for_CNAME = _params_for_single
    _params_for_DNAME = _params_for_single
    _params_for_PTR = _params_for_single

    def _params_for_MX(self, record):
        return {
            'rrset_name': self._record_name(record.name),
            'rrset_ttl': record.ttl,
            'rrset_type': record._type,
            'rrset_values': ['{} {}'.format(v.preference, v.exchange)
                             for v in record.values]
        }

    def _params_for_SRV(self, record):
        return {
            'rrset_name': self._record_name(record.name),
            'rrset_ttl': record.ttl,
            'rrset_type': record._type,
            'rrset_values': ['{} {} {} {}'.format(v.priority, v.weight, v.port,
                             v.target) for v in record.values]
        }

    def _params_for_SSHFP(self, record):
        return {
            'rrset_name': self._record_name(record.name),
            'rrset_ttl': record.ttl,
            'rrset_type': record._type,
            'rrset_values': ['{} {} {}'.format(v.algorithm, v.fingerprint_type,
                             v.fingerprint) for v in record.values]
        }

    def _apply_create(self, change):
        new = change.new
        data = getattr(self, '_params_for_{}'.format(new._type))(new)
        self._client.record_create(new.zone.name[:-1], data)

    def _apply_update(self, change):
        self._apply_delete(change)
        self._apply_create(change)

    def _apply_delete(self, change):
        existing = change.existing
        zone = existing.zone
        self._client.record_delete(zone.name[:-1],
                                   self._record_name(existing.name),
                                   existing._type)

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        zone = desired.name[:-1]
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        try:
            self._client.zone(zone)
        except GandiClientNotFound:
            self.log.info('_apply: no existing zone, trying to create it')
            try:
                self._client.zone_create(zone)
                self.log.info('_apply: zone has been successfully created')
            except GandiClientNotFound:
                # We suppress existing exception before raising
                # GandiClientUnknownDomainName.
                e = GandiClientUnknownDomainName('This domain is not '
                                                 'registred at Gandi. '
                                                 'Please register or '
                                                 'transfer it here '
                                                 'to be able to manage its '
                                                 'DNS zone.')
                e.__cause__ = None
                raise e

        # Force records deletion to be done before creation in order to avoid
        # "CNAME record must be the only record" error when an existing CNAME
        # record is replaced by an A/AAAA record.
        changes.reverse()

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name.lower()))(change)

        # Clear out the cache if any
        self._zone_records.pop(desired.name, None)
