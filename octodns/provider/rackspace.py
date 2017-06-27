#
#
#


from __future__ import absolute_import, division, print_function, \
    unicode_literals

from requests import HTTPError, Session, post
import json
import logging

from ..record import Create, Record
from .base import BaseProvider


class RackspaceProvider(BaseProvider):
    SUPPORTS_GEO = False
    TIMEOUT = 5

    def __init__(self, username, api_key, *args, **kwargs):
        '''
        Rackspace API v1 Provider

        rackspace:
            class: octodns.provider.rackspace.RackspaceProvider
            # The the username to authenticate with (required)
            username: username
            # The api key that grants access for that user (required)
            api_key: api-key
        '''
        self.log = logging.getLogger('RackspaceProvider[{}]'.format(username))
        super(RackspaceProvider, self).__init__(id, *args, **kwargs)

        auth_token, dns_endpoint = self._get_auth_token(username, api_key)
        self.dns_endpoint = dns_endpoint

        sess = Session()
        sess.headers.update({'X-Auth-Token': auth_token})
        self._sess = sess

    def _get_auth_token(self, username, api_key):
        ret = post('https://identity.api.rackspacecloud.com/v2.0/tokens',
                   json={"auth": {"RAX-KSKEY:apiKeyCredentials": {"username": username, "apiKey": api_key}}},
                   )
        cloud_dns_endpoint = [x for x in ret.json()['access']['serviceCatalog'] if x['name'] == 'cloudDNS'][0]['endpoints'][0]['publicURL']
        return ret.json()['access']['token']['id'], cloud_dns_endpoint

    def _get_zone_id_for(self, zone_name):
        ret = self._request('GET', 'domains', pagination_key='domains')
        if ret and 'name' in ret:
            return [x for x in ret if x['name'] == zone_name][0]['id']
        else:
            return None

    def _request(self, method, path, data=None, pagination_key=None):
        self.log.debug('_request: method=%s, path=%s', method, path)
        url = '{}/{}'.format(self.dns_endpoint, path)

        if pagination_key:
            return self._paginated_request_for_url(method, url, data, pagination_key)
        else:
            return self._request_for_url(method, url, data)

    def _request_for_url(self, method, url, data):
        resp = self._sess.request(method, url, json=data, timeout=self.TIMEOUT)
        self.log.debug('_request:   status=%d', resp.status_code)
        resp.raise_for_status()
        return resp

    def _paginated_request_for_url(self, method, url, data, pagination_key):
        acc = []

        resp = self._sess.request(method, url, json=data, timeout=self.TIMEOUT)
        self.log.debug('_request:   status=%d', resp.status_code)
        resp.raise_for_status()
        acc.extend(resp.json()[pagination_key])

        next_page = [x for x in resp.json().get('links', []) if x['rel'] == 'next']
        if next_page:
            url = next_page[0]['href']
            return acc.extend(self._paginated_request_for_url(method, url, data, pagination_key))
        else:
            return acc

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

    def _data_for_single(self, record):
        return {
            'type': record['type'],
            'value': record['data'],
            'ttl': record['ttl']
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
            priority, value = record['content'].split(' ', 1)
            values.append({
                'priority': priority,
                'value': value,
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

    def populate(self, zone, target=False):
        self.log.debug('populate: name=%s', zone.name)
        resp = None
        try:
            domain_id = self._get_zone_id_for(zone.name)
            resp = self._request('GET', '/domains/{}/records'.format(domain_id), pagination_key='records')
            self.log.debug('populate:   loaded')
        except HTTPError as e:
            if e.response.status_code == 401:
                # Nicer error message for auth problems
                raise Exception('Rackspace request unauthorized')
            elif e.response.status_code == 422:
                # 422 means powerdns doesn't know anything about the requsted
                # domain. We'll just ignore it here and leave the zone
                # untouched.
                pass
            else:
                # just re-throw
                raise

        before = len(zone.records)

        if resp:
            for record in resp.json()['records']:
                record_type = record['type']
                if record_type == 'SOA':
                    continue
                data_for = getattr(self, '_data_for_{}'.format(record_type))
                record_name = zone.hostname_from_fqdn(record['name'])
                record = Record.new(zone, record_name, data_for(record),
                                    source=self)
                zone.add_record(record)

        self.log.info('populate:   found %s records',
                      len(zone.records) - before)

    def _records_for_multiple(self, record):
        return [{'content': v, 'disabled': False}
                for v in record.values]

    _records_for_A = _records_for_multiple
    _records_for_AAAA = _records_for_multiple
    _records_for_NS = _records_for_multiple

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
            'content': '{} {}'.format(v.priority, v.value),
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

    def _extra_changes(self, existing, _):
        self.log.debug('_extra_changes: zone=%s', existing.name)

        ns = self._get_nameserver_record(existing)
        if not ns:
            return []

        # sorting mostly to make things deterministic for testing, but in
        # theory it let us find what we're after quickier (though sorting would
        # ve more exepensive.)
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
            if e.response.status_code != 422 or \
                    not error.startswith('Could not find domain '):
                self.log.error('_apply:   status=%d, text=%s',
                               e.response.status_code,
                               e.response.text)
                raise
            self.log.info('_apply:   creating zone=%s', desired.name)
            # 422 means powerdns doesn't know anything about the requsted
            # domain. We'll try to create it with the correct records instead
            # of update. Hopefully all the mods are creates :-)
            data = {
                'name': desired.name,
                'kind': 'Master',
                'masters': [],
                'nameservers': [],
                'rrsets': mods,
                'soa_edit_api': 'INCEPTION-INCREMENT',
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


