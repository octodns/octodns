#
#
#
from __future__ import absolute_import, division, print_function, \
    unicode_literals

from requests import HTTPError, Session, post
from collections import defaultdict
import logging
import time

from ..record import Record
from .base import BaseProvider


def _value_keyer(v):
    return (v.get('type', ''), v['name'], v.get('data', ''))


def add_trailing_dot(s):
    assert s
    assert s[-1] != '.'
    return s + '.'


def remove_trailing_dot(s):
    assert s
    assert s[-1] == '.'
    return s[:-1]


def escape_semicolon(s):
    assert s
    return s.replace(';', '\\;')


def unescape_semicolon(s):
    assert s
    return s.replace('\\;', ';')


class RackspaceProvider(BaseProvider):
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS_ROOT_NS = False
    SUPPORTS = set(('A', 'AAAA', 'ALIAS', 'CNAME', 'MX', 'NS', 'PTR', 'SPF',
                    'TXT'))
    TIMEOUT = 5

    def __init__(self, id, username, api_key, ratelimit_delay=0.0, *args,
                 **kwargs):
        '''
        Rackspace API v1 Provider

        rackspace:
            class: octodns.provider.rackspace.RackspaceProvider
            # The the username to authenticate with (required)
            username: username
            # The api key that grants access for that user (required)
            api_key: api-key
        '''
        self.log = logging.getLogger('RackspaceProvider[{}]'.format(id))
        super(RackspaceProvider, self).__init__(id, *args, **kwargs)

        auth_token, dns_endpoint = self._get_auth_token(username, api_key)
        self.dns_endpoint = dns_endpoint

        self.ratelimit_delay = float(ratelimit_delay)

        sess = Session()
        sess.headers.update({'X-Auth-Token': auth_token})
        self._sess = sess

        # Map record type, name, and data to an id when populating so that
        # we can find the id for update and delete operations.
        self._id_map = {}

    def _get_auth_token(self, username, api_key):
        ret = post('https://identity.api.rackspacecloud.com/v2.0/tokens',
                   json={"auth": {
                       "RAX-KSKEY:apiKeyCredentials": {"username": username,
                                                       "apiKey": api_key}}},
                   )
        cloud_dns_endpoint = \
            [x for x in ret.json()['access']['serviceCatalog'] if
             x['name'] == 'cloudDNS'][0]['endpoints'][0]['publicURL']
        return ret.json()['access']['token']['id'], cloud_dns_endpoint

    def _get_zone_id_for(self, zone):
        ret = self._request('GET', 'domains', pagination_key='domains')
        return [x for x in ret if x['name'] == zone.name[:-1]][0]['id']

    def _request(self, method, path, data=None, pagination_key=None):
        self.log.debug('_request: method=%s, path=%s', method, path)
        url = '{}/{}'.format(self.dns_endpoint, path)

        if pagination_key:
            resp = self._paginated_request_for_url(method, url, data,
                                                   pagination_key)
        else:
            resp = self._request_for_url(method, url, data)
        time.sleep(self.ratelimit_delay)
        return resp

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

        next_page = [x for x in resp.json().get('links', []) if
                     x['rel'] == 'next']
        if next_page:
            url = next_page[0]['href']
            acc.extend(self._paginated_request_for_url(method, url, data,
                                                       pagination_key))
            return acc
        else:
            return acc

    def _post(self, path, data=None):
        return self._request('POST', path, data=data)

    def _put(self, path, data=None):
        return self._request('PUT', path, data=data)

    def _delete(self, path, data=None):
        return self._request('DELETE', path, data=data)

    @classmethod
    def _key_for_record(cls, rs_record):
        return rs_record['type'], rs_record['name'], rs_record['data']

    def _data_for_multiple(self, rrset):
        return {
            'type': rrset[0]['type'],
            'values': [r['data'] for r in rrset],
            'ttl': rrset[0]['ttl']
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple

    def _data_for_NS(self, rrset):
        return {
            'type': rrset[0]['type'],
            'values': [add_trailing_dot(r['data']) for r in rrset],
            'ttl': rrset[0]['ttl']
        }

    def _data_for_single(self, record):
        return {
            'type': record[0]['type'],
            'value': add_trailing_dot(record[0]['data']),
            'ttl': record[0]['ttl']
        }

    _data_for_ALIAS = _data_for_single
    _data_for_CNAME = _data_for_single
    _data_for_PTR = _data_for_single

    def _data_for_textual(self, rrset):
        return {
            'type': rrset[0]['type'],
            'values': [escape_semicolon(r['data']) for r in rrset],
            'ttl': rrset[0]['ttl']
        }

    _data_for_SPF = _data_for_textual
    _data_for_TXT = _data_for_textual

    def _data_for_MX(self, rrset):
        values = []
        for record in rrset:
            values.append({
                'priority': record['priority'],
                'value': add_trailing_dot(record['data']),
            })
        return {
            'type': rrset[0]['type'],
            'values': values,
            'ttl': rrset[0]['ttl']
        }

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s', zone.name)
        resp_data = None
        try:
            domain_id = self._get_zone_id_for(zone)
            resp_data = self._request('GET',
                                      'domains/{}/records'.format(domain_id),
                                      pagination_key='records')
            self.log.debug('populate:   loaded')
        except HTTPError as e:
            if e.response.status_code == 401:
                # Nicer error message for auth problems
                raise Exception('Rackspace request unauthorized')
            elif e.response.status_code == 404:
                # Zone not found leaves the zone empty instead of failing.
                return False
            raise

        before = len(zone.records)

        if resp_data:
            records = self._group_records(resp_data)
            for record_type, records_of_type in records.items():
                for raw_record_name, record_set in records_of_type.items():
                    data_for = getattr(self,
                                       '_data_for_{}'.format(record_type))
                    record_name = zone.hostname_from_fqdn(raw_record_name)
                    record = Record.new(zone, record_name,
                                        data_for(record_set),
                                        source=self)
                    zone.add_record(record, lenient=lenient)

        self.log.info('populate:   found %s records, exists=True',
                      len(zone.records) - before)
        return True

    def _group_records(self, all_records):
        records = defaultdict(lambda: defaultdict(list))
        for record in all_records:
            self._id_map[self._key_for_record(record)] = record['id']
            records[record['type']][record['name']].append(record)
        return records

    @staticmethod
    def _record_for_single(record, value):
        return {
            'name': remove_trailing_dot(record.fqdn),
            'type': record._type,
            'data': value,
            'ttl': max(record.ttl, 300),
        }

    _record_for_A = _record_for_single
    _record_for_AAAA = _record_for_single

    @staticmethod
    def _record_for_named(record, value):
        return {
            'name': remove_trailing_dot(record.fqdn),
            'type': record._type,
            'data': remove_trailing_dot(value),
            'ttl': max(record.ttl, 300),
        }

    _record_for_NS = _record_for_named
    _record_for_ALIAS = _record_for_named
    _record_for_CNAME = _record_for_named
    _record_for_PTR = _record_for_named

    @staticmethod
    def _record_for_textual(record, value):
        return {
            'name': remove_trailing_dot(record.fqdn),
            'type': record._type,
            'data': unescape_semicolon(value),
            'ttl': max(record.ttl, 300),
        }

    _record_for_SPF = _record_for_textual
    _record_for_TXT = _record_for_textual

    @staticmethod
    def _record_for_MX(record, value):
        return {
            'name': remove_trailing_dot(record.fqdn),
            'type': record._type,
            'data': remove_trailing_dot(value.exchange),
            'ttl': max(record.ttl, 300),
            'priority': value.preference
        }

    def _get_values(self, record):
        try:
            return record.values
        except AttributeError:
            return [record.value]

    def _mod_Create(self, change):
        return self._create_given_change_values(change,
                                                self._get_values(change.new))

    def _create_given_change_values(self, change, values):
        transformer = getattr(self, "_record_for_{}".format(change.new._type))
        return [transformer(change.new, v) for v in values]

    def _mod_Update(self, change):
        existing_values = self._get_values(change.existing)
        new_values = self._get_values(change.new)

        # A reduction in number of values in an update record needs
        # to get upgraded into a Delete change for the removed values.
        deleted_values = set(existing_values) - set(new_values)
        delete_out = self._delete_given_change_values(change, deleted_values)

        # An increase in number of values in an update record needs
        # to get upgraded into a Create change for the added values.
        create_values = set(new_values) - set(existing_values)
        create_out = self._create_given_change_values(change, create_values)

        update_out = []
        update_values = set(new_values).intersection(set(existing_values))
        for value in update_values:
            transformer = getattr(self,
                                  "_record_for_{}".format(change.new._type))
            prior_rs_record = transformer(change.existing, value)
            prior_key = self._key_for_record(prior_rs_record)
            next_rs_record = transformer(change.new, value)
            next_key = self._key_for_record(next_rs_record)
            next_rs_record["id"] = self._id_map[prior_key]
            del next_rs_record["type"]
            update_out.append(next_rs_record)
            self._id_map[next_key] = self._id_map[prior_key]
            del self._id_map[prior_key]
        return create_out, update_out, delete_out

    def _mod_Delete(self, change):
        return self._delete_given_change_values(change, self._get_values(
            change.existing))

    def _delete_given_change_values(self, change, values):
        transformer = getattr(self, "_record_for_{}".format(
            change.existing._type))
        out = []
        for value in values:
            rs_record = transformer(change.existing, value)
            key = self._key_for_record(rs_record)
            out.append('id=' + self._id_map[key])
            del self._id_map[key]
        return out

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        # Creates, updates, and deletes are processed by different endpoints
        # and are broken out by record-set entries; pre-process everything
        # into these buckets in order to minimize the number of API calls.
        domain_id = self._get_zone_id_for(desired)
        creates = []
        updates = []
        deletes = []
        for change in changes:
            if change.__class__.__name__ == 'Create':
                creates += self._mod_Create(change)
            elif change.__class__.__name__ == 'Update':
                add_creates, add_updates, add_deletes = self._mod_Update(
                    change)
                creates += add_creates
                updates += add_updates
                deletes += add_deletes
            else:
                assert change.__class__.__name__ == 'Delete'
                deletes += self._mod_Delete(change)

        if deletes:
            params = "&".join(sorted(deletes))
            self._delete('domains/{}/records?{}'.format(domain_id, params))

        if updates:
            data = {"records": sorted(updates, key=_value_keyer)}
            self._put('domains/{}/records'.format(domain_id), data=data)

        if creates:
            data = {"records": sorted(creates, key=_value_keyer)}
            self._post('domains/{}/records'.format(domain_id), data=data)
