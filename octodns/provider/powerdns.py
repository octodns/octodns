#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from requests import HTTPError, Session
import logging

from ..record import Create, Record
from .base import BaseProvider


class PowerDnsBaseProvider(BaseProvider):
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS_ROOT_NS = False
    SUPPORTS = set(('A', 'AAAA', 'ALIAS', 'CAA', 'CNAME', 'MX', 'NAPTR', 'NS',
                    'PTR', 'SPF', 'SSHFP', 'SRV', 'TXT'))
    TIMEOUT = 5

    def __init__(self, id, host, api_key, port=8081,
                 scheme="http", timeout=TIMEOUT, *args, **kwargs):
        super(PowerDnsBaseProvider, self).__init__(id, *args, **kwargs)

        self.host = host
        self.port = port
        self.scheme = scheme
        self.timeout = timeout

        self._powerdns_version = None

        sess = Session()
        sess.headers.update({'X-API-Key': api_key})
        self._sess = sess

    def _request(self, method, path, data=None):
        self.log.debug('_request: method=%s, path=%s', method, path)

        url = '{}://{}:{}/api/v1/servers/localhost/{}' \
            .format(self.scheme, self.host, self.port, path).rstrip("/")
        # Strip trailing / from url.
        resp = self._sess.request(method, url, json=data, timeout=self.timeout)
        self.log.debug('_request:   status=%d', resp.status_code)
        resp.raise_for_status()
        return resp

    def _get(self, path, data=None):
        return self._request('GET', path, data=data)

    def _post(self, path, data=None):
        return self._request('POST', path, data=data)

    def _patch(self, path, data=None):
        return self._request('PATCH', path, data=data)

    def _data_for_multiple(self, rrset):
        # TODO: geo not supported
        return {
            'type': rrset['type'],
            'values': [r['content'] for r in rrset['records']],
            'ttl': rrset['ttl']
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple
    _data_for_NS = _data_for_multiple

    def _data_for_CAA(self, rrset):
        values = []
        for record in rrset['records']:
            flags, tag, value = record['content'].split(' ', 2)
            values.append({
                'flags': flags,
                'tag': tag,
                'value': value[1:-1],
            })
        return {
            'type': rrset['type'],
            'values': values,
            'ttl': rrset['ttl']
        }

    def _data_for_single(self, rrset):
        return {
            'type': rrset['type'],
            'value': rrset['records'][0]['content'],
            'ttl': rrset['ttl']
        }

    _data_for_ALIAS = _data_for_single
    _data_for_CNAME = _data_for_single
    _data_for_PTR = _data_for_single

    def _data_for_quoted(self, rrset):
        return {
            'type': rrset['type'],
            'values': [r['content'][1:-1] for r in rrset['records']],
            'ttl': rrset['ttl']
        }

    _data_for_SPF = _data_for_quoted
    _data_for_TXT = _data_for_quoted

    def _data_for_MX(self, rrset):
        values = []
        for record in rrset['records']:
            preference, exchange = record['content'].split(' ', 1)
            values.append({
                'preference': preference,
                'exchange': exchange,
            })
        return {
            'type': rrset['type'],
            'values': values,
            'ttl': rrset['ttl']
        }

    def _data_for_NAPTR(self, rrset):
        values = []
        for record in rrset['records']:
            order, preference, flags, service, regexp, replacement = \
                record['content'].split(' ', 5)
            values.append({
                'order': order,
                'preference': preference,
                'flags': flags[1:-1],
                'service': service[1:-1],
                'regexp': regexp[1:-1],
                'replacement': replacement,
            })
        return {
            'type': rrset['type'],
            'values': values,
            'ttl': rrset['ttl']
        }

    def _data_for_SSHFP(self, rrset):
        values = []
        for record in rrset['records']:
            algorithm, fingerprint_type, fingerprint = \
                record['content'].split(' ', 2)
            values.append({
                'algorithm': algorithm,
                'fingerprint_type': fingerprint_type,
                'fingerprint': fingerprint,
            })
        return {
            'type': rrset['type'],
            'values': values,
            'ttl': rrset['ttl']
        }

    def _data_for_SRV(self, rrset):
        values = []
        for record in rrset['records']:
            priority, weight, port, target = \
                record['content'].split(' ', 3)
            values.append({
                'priority': priority,
                'weight': weight,
                'port': port,
                'target': target,
            })
        return {
            'type': rrset['type'],
            'values': values,
            'ttl': rrset['ttl']
        }

    @property
    def powerdns_version(self):
        if self._powerdns_version is None:
            try:
                resp = self._get('')
            except HTTPError as e:
                if e.response.status_code == 401:
                    # Nicer error message for auth problems
                    raise Exception('PowerDNS unauthorized host={}'
                                    .format(self.host))
                raise

            version = resp.json()['version']
            self.log.debug('powerdns_version: got version %s from server',
                           version)
            self._powerdns_version = [int(p) for p in version.split('.')]

        return self._powerdns_version

    @property
    def soa_edit_api(self):
        # >>> [4, 4, 3] >= [4, 3]
        # True
        # >>> [4, 3, 3] >= [4, 3]
        # True
        # >>> [4, 1, 3] >= [4, 3]
        # False
        if self.powerdns_version >= [4, 3]:
            return 'DEFAULT'
        return 'INCEPTION-INCREMENT'

    @property
    def check_status_not_found(self):
        # >=4.2.x returns 404 when not found
        return self.powerdns_version >= [4, 2]

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        resp = None
        try:
            resp = self._get('zones/{}'.format(zone.name))
            self.log.debug('populate:   loaded')
        except HTTPError as e:
            error = self._get_error(e)
            if e.response.status_code == 401:
                # Nicer error message for auth problems
                raise Exception('PowerDNS unauthorized host={}'
                                .format(self.host))
            elif e.response.status_code == 404 \
                    and self.check_status_not_found:
                # 404 means powerdns doesn't know anything about the requested
                # domain. We'll just ignore it here and leave the zone
                # untouched.
                pass
            elif e.response.status_code == 422 \
                    and error.startswith('Could not find domain ') \
                    and not self.check_status_not_found:
                # 422 means powerdns doesn't know anything about the requested
                # domain. We'll just ignore it here and leave the zone
                # untouched.
                pass
            else:
                # just re-throw
                raise

        before = len(zone.records)
        exists = False

        if resp:
            exists = True
            for rrset in resp.json()['rrsets']:
                _type = rrset['type']
                if _type == 'SOA':
                    continue
                data_for = getattr(self, '_data_for_{}'.format(_type))
                record_name = zone.hostname_from_fqdn(rrset['name'])
                record = Record.new(zone, record_name, data_for(rrset),
                                    source=self, lenient=lenient)
                zone.add_record(record, lenient=lenient)

        self.log.info('populate:   found %s records, exists=%s',
                      len(zone.records) - before, exists)
        return exists

    def _records_for_multiple(self, record):
        return [{'content': v, 'disabled': False}
                for v in record.values]

    _records_for_A = _records_for_multiple
    _records_for_AAAA = _records_for_multiple
    _records_for_NS = _records_for_multiple

    def _records_for_CAA(self, record):
        return [{
            'content': '{} {} "{}"'.format(v.flags, v.tag, v.value),
            'disabled': False
        } for v in record.values]

    def _records_for_single(self, record):
        return [{'content': record.value, 'disabled': False}]

    _records_for_ALIAS = _records_for_single
    _records_for_CNAME = _records_for_single
    _records_for_PTR = _records_for_single

    def _records_for_quoted(self, record):
        return [{'content': '"{}"'.format(v), 'disabled': False}
                for v in record.values]

    _records_for_SPF = _records_for_quoted
    _records_for_TXT = _records_for_quoted

    def _records_for_MX(self, record):
        return [{
            'content': '{} {}'.format(v.preference, v.exchange),
            'disabled': False
        } for v in record.values]

    def _records_for_NAPTR(self, record):
        return [{
            'content': '{} {} "{}" "{}" "{}" {}'.format(v.order, v.preference,
                                                        v.flags, v.service,
                                                        v.regexp,
                                                        v.replacement),
            'disabled': False
        } for v in record.values]

    def _records_for_SSHFP(self, record):
        return [{
            'content': '{} {} {}'.format(v.algorithm, v.fingerprint_type,
                                         v.fingerprint),
            'disabled': False
        } for v in record.values]

    def _records_for_SRV(self, record):
        return [{
            'content': '{} {} {} {}'.format(v.priority, v.weight, v.port,
                                            v.target),
            'disabled': False
        } for v in record.values]

    def _mod_Create(self, change):
        new = change.new
        records_for = getattr(self, '_records_for_{}'.format(new._type))
        return {
            'name': new.fqdn,
            'type': new._type,
            'ttl': new.ttl,
            'changetype': 'REPLACE',
            'records': records_for(new)
        }

    _mod_Update = _mod_Create

    def _mod_Delete(self, change):
        existing = change.existing
        records_for = getattr(self, '_records_for_{}'.format(existing._type))
        return {
            'name': existing.fqdn,
            'type': existing._type,
            'ttl': existing.ttl,
            'changetype': 'DELETE',
            'records': records_for(existing)
        }

    def _get_nameserver_record(self, existing):
        return None

    def _extra_changes(self, existing, **kwargs):
        self.log.debug('_extra_changes: zone=%s', existing.name)

        ns = self._get_nameserver_record(existing)
        if not ns:
            return []

        # sorting mostly to make things deterministic for testing, but in
        # theory it let us find what we're after quicker (though sorting would
        # be more expensive.)
        for record in sorted(existing.records):
            if record == ns:
                # We've found the top-level NS record, return any changes
                change = record.changes(ns, self)
                self.log.debug('_extra_changes:   change=%s', change)
                if change:
                    # We need to modify an existing record
                    return [change]
                # No change is necessary
                return []
        # No existing top-level NS
        self.log.debug('_extra_changes:   create')
        return [Create(ns)]

    def _get_error(self, http_error):
        try:
            return http_error.response.json()['error']
        except Exception:
            return ''

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        mods = []
        for change in changes:
            class_name = change.__class__.__name__
            mods.append(getattr(self, '_mod_{}'.format(class_name))(change))
        self.log.debug('_apply:   sending change request')

        try:
            self._patch('zones/{}'.format(desired.name),
                        data={'rrsets': mods})
            self.log.debug('_apply:   patched')
        except HTTPError as e:
            error = self._get_error(e)
            if not (
                (
                    e.response.status_code == 404 and
                    self.check_status_not_found
                ) or (
                    e.response.status_code == 422 and
                    error.startswith('Could not find domain ') and
                    not self.check_status_not_found
                )
            ):
                self.log.error(
                    '_apply:   status=%d, text=%s',
                    e.response.status_code,
                    e.response.text)
                raise

            self.log.info('_apply:   creating zone=%s', desired.name)
            # 404 or 422 means powerdns doesn't know anything about the
            # requested domain. We'll try to create it with the correct
            # records instead of update. Hopefully all the mods are
            # creates :-)
            data = {
                'name': desired.name,
                'kind': 'Master',
                'masters': [],
                'nameservers': [],
                'rrsets': mods,
                'soa_edit_api': self.soa_edit_api,
                'serial': 0,
            }
            try:
                self._post('zones', data)
            except HTTPError as e:
                self.log.error('_apply:   status=%d, text=%s',
                               e.response.status_code,
                               e.response.text)
                raise
            self.log.debug('_apply:   created')

        self.log.debug('_apply:   complete')


class PowerDnsProvider(PowerDnsBaseProvider):
    '''
    PowerDNS API v4 Provider

    powerdns:
        class: octodns.provider.powerdns.PowerDnsProvider
        # The host on which PowerDNS api is listening (required)
        host: fqdn
        # The api key that grans access (required)
        api_key: api-key
        # The port on which PowerDNS api is listening (optional, default 8081)
        port: 8081
        # The nameservers to use for this provider (optional,
        #   default unmanaged)
        nameserver_values:
            - 1.2.3.4.
            - 1.2.3.5.
        # The nameserver record TTL when managed, (optional, default 600)
        nameserver_ttl: 600
    '''

    def __init__(self, id, host, api_key, port=8081, nameserver_values=None,
                 nameserver_ttl=600,
                 *args, **kwargs):
        self.log = logging.getLogger('PowerDnsProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, host=%s, port=%d, '
                       'nameserver_values=%s, nameserver_ttl=%d',
                       id, host, port, nameserver_values, nameserver_ttl)
        super(PowerDnsProvider, self).__init__(id, host=host, api_key=api_key,
                                               port=port,
                                               *args, **kwargs)

        self.nameserver_values = nameserver_values
        self.nameserver_ttl = nameserver_ttl

    def _get_nameserver_record(self, existing):
        if self.nameserver_values:
            return Record.new(existing, '', {
                'type': 'NS',
                'ttl': self.nameserver_ttl,
                'values': self.nameserver_values,
            }, source=self)

        return super(PowerDnsProvider, self)._get_nameserver_record(existing)
