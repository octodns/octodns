#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict
from copy import deepcopy
from logging import getLogger
from requests import Session

from ..record import Record, Update
from .base import BaseProvider


class CloudflareError(Exception):
    def __init__(self, data):
        try:
            message = data['errors'][0]['message']
        except (IndexError, KeyError):
            message = 'Cloudflare error'
        super(CloudflareError, self).__init__(message)


class CloudflareAuthenticationError(CloudflareError):
    def __init__(self, data):
        CloudflareError.__init__(self, data)


_PROXIABLE_RECORD_TYPES = {'A', 'AAAA', 'CNAME'}


class CloudflareProvider(BaseProvider):
    '''
    Cloudflare DNS provider

    cloudflare:
        class: octodns.provider.cloudflare.CloudflareProvider
        # Your Cloudflare account email address (required)
        email: dns-manager@example.com
        # The api key (required)
        token: foo
        # Import CDN enabled records as CNAME to {}.cdn.cloudflare.net. Records
        # ending at .cdn.cloudflare.net. will be ignored when this provider is
        # not used as the source and the cdn option is enabled.
        #
        # See: https://support.cloudflare.com/hc/en-us/articles/115000830351
        cdn: false

    Note: The "proxied" flag of "A", "AAAA" and "CNAME" records can be managed
          via the YAML provider like so:
              name:
                octodons:
                  cloudflare:
                    proxied: true
                ttl: 120
                type: A
                value: 1.2.3.4
    '''
    SUPPORTS_GEO = False
    SUPPORTS = set(('ALIAS', 'A', 'AAAA', 'CAA', 'CNAME', 'MX', 'NS', 'SRV',
                    'SPF', 'TXT'))

    MIN_TTL = 120
    TIMEOUT = 15

    def __init__(self, id, email, token, cdn=False, *args, **kwargs):
        self.log = getLogger('CloudflareProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, email=%s, token=***, cdn=%s', id,
                       email, cdn)
        super(CloudflareProvider, self).__init__(id, *args, **kwargs)

        sess = Session()
        sess.headers.update({
            'X-Auth-Email': email,
            'X-Auth-Key': token,
        })
        self.cdn = cdn
        self._sess = sess

        self._zones = None
        self._zone_records = {}

    def _request(self, method, path, params=None, data=None):
        self.log.debug('_request: method=%s, path=%s', method, path)

        url = 'https://api.cloudflare.com/client/v4{}'.format(path)
        resp = self._sess.request(method, url, params=params, json=data,
                                  timeout=self.TIMEOUT)
        self.log.debug('_request:   status=%d', resp.status_code)
        if resp.status_code == 400:
            raise CloudflareError(resp.json())
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

    def _data_for_cdn(self, name, _type, records):
        self.log.info('CDN rewrite for %s', records[0]['name'])
        _type = "CNAME"
        if name == "":
            _type = "ALIAS"

        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'value': '{}.cdn.cloudflare.net.'.format(records[0]['name']),
        }

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
            'values': [r['content'].replace(';', '\\;') for r in records],
        }

    def _data_for_CAA(self, _type, records):
        values = []
        for r in records:
            data = r['data']
            values.append(data)
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

    _data_for_ALIAS = _data_for_CNAME

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

    def _data_for_SRV(self, _type, records):
        values = []
        for r in records:
            values.append({
                'priority': r['data']['priority'],
                'weight': r['data']['weight'],
                'port': r['data']['port'],
                'target': '{}.'.format(r['data']['target']),
            })
        return {
            'type': _type,
            'ttl': records[0]['ttl'],
            'values': values
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

    def _record_for(self, zone, name, _type, records, lenient):
        # rewrite Cloudflare proxied records
        if self.cdn and records[0]['proxied']:
            data = self._data_for_cdn(name, _type, records)
        else:
            # Cloudflare supports ALIAS semantics with root CNAMEs
            if _type == 'CNAME' and name == '':
                _type = 'ALIAS'

            data_for = getattr(self, '_data_for_{}'.format(_type))
            data = data_for(_type, records)

        record = Record.new(zone, name, data, source=self, lenient=lenient)

        if _type in _PROXIABLE_RECORD_TYPES:
            record._octodns['cloudflare'] = {
                'proxied': records[0].get('proxied', False)
            }

        return record

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        exists = False
        before = len(zone.records)
        records = self.zone_records(zone)
        if records:
            exists = True
            values = defaultdict(lambda: defaultdict(list))
            for record in records:
                name = zone.hostname_from_fqdn(record['name'])
                _type = record['type']
                if _type in self.SUPPORTS:
                    values[name][record['type']].append(record)

            for name, types in values.items():
                for _type, records in types.items():
                    record = self._record_for(zone, name, _type, records,
                                              lenient)

                    # only one rewrite is needed for names where the proxy is
                    # enabled at multiple records with a different type but
                    # the same name
                    if (self.cdn and records[0]['proxied'] and
                       record in zone._records[name]):
                        self.log.info('CDN rewrite %s already in zone', name)
                        continue

                    zone.add_record(record, lenient=lenient)

        self.log.info('populate:   found %s records, exists=%s',
                      len(zone.records) - before, exists)
        return exists

    def _include_change(self, change):
        if isinstance(change, Update):
            new = change.new.data

            # Cloudflare manages TTL of proxied records, so we should exclude
            # TTL from the comparison (to prevent false-positives).
            if self._record_is_proxied(change.existing):
                existing = deepcopy(change.existing.data)
                existing.update({
                    'ttl': new['ttl']
                })
            else:
                existing = change.existing.data

            new['ttl'] = max(self.MIN_TTL, new['ttl'])
            if new == existing:
                return False

        # If this is a record to enable Cloudflare CDN don't update as
        # we don't know the original values.
        if (change.record._type in ('ALIAS', 'CNAME') and
                change.record.value.endswith('.cdn.cloudflare.net.')):
            return False

        return True

    def _contents_for_multiple(self, record):
        for value in record.values:
            yield {'content': value}

    _contents_for_A = _contents_for_multiple
    _contents_for_AAAA = _contents_for_multiple
    _contents_for_NS = _contents_for_multiple
    _contents_for_SPF = _contents_for_multiple

    def _contents_for_CAA(self, record):
        for value in record.values:
            yield {
                'data': {
                    'flags': value.flags,
                    'tag': value.tag,
                    'value': value.value,
                }
            }

    def _contents_for_TXT(self, record):
        for value in record.values:
            yield {'content': value.replace('\\;', ';')}

    def _contents_for_CNAME(self, record):
        yield {'content': record.value}

    def _contents_for_MX(self, record):
        for value in record.values:
            yield {
                'priority': value.preference,
                'content': value.exchange
            }

    def _contents_for_SRV(self, record):
        service, proto = record.name.split('.', 2)
        for value in record.values:
            yield {
                'data': {
                    'service': service,
                    'proto': proto,
                    'name': record.zone.name,
                    'priority': value.priority,
                    'weight': value.weight,
                    'port': value.port,
                    'target': value.target[:-1],
                }
            }

    def _record_is_proxied(self, record):
        return (
            not self.cdn and
            record._octodns.get('cloudflare', {}).get('proxied', False)
        )

    def _gen_data(self, record):
        name = record.fqdn[:-1]
        _type = record._type
        ttl = max(self.MIN_TTL, record.ttl)

        # Cloudflare supports ALIAS semantics with a root CNAME
        if _type == 'ALIAS':
            _type = 'CNAME'

        contents_for = getattr(self, '_contents_for_{}'.format(_type))
        for content in contents_for(record):
            content.update({
                'name': name,
                'type': _type,
                'ttl': ttl,
            })

            if _type in _PROXIABLE_RECORD_TYPES:
                content.update({
                    'proxied': self._record_is_proxied(record)
                })

            yield content

    def _gen_key(self, data):
        # Note that most CF record data has a `content` field the value of
        # which is a unique/hashable string for the record's. It includes all
        # the "value" bits, but not the secondary stuff like TTL's. E.g.  for
        # an A it'll include the value, for a CAA it'll include the flags, tag,
        # and value, ... We'll take advantage of this to try and match up old &
        # new records cleanly. In general when there are multiple records for a
        # name & type each will have a distinct/consistent `content` that can
        # serve as a unique identifier.
        # BUT... there are exceptions. MX, CAA, and SRV don't have a simple
        # content as things are currently implemented so we need to handle
        # those explicitly and create unique/hashable strings for them.
        _type = data['type']
        if _type == 'MX':
            return '{priority} {content}'.format(**data)
        elif _type == 'CAA':
            data = data['data']
            return '{flags} {tag} {value}'.format(**data)
        elif _type == 'SRV':
            data = data['data']
            return '{port} {priority} {target} {weight}'.format(**data)
        return data['content']

    def _apply_Create(self, change):
        new = change.new
        zone_id = self.zones[new.zone.name]
        path = '/zones/{}/dns_records'.format(zone_id)
        for content in self._gen_data(new):
            self._request('POST', path, data=content)

    def _apply_Update(self, change):
        zone = change.new.zone
        zone_id = self.zones[zone.name]
        hostname = zone.hostname_from_fqdn(change.new.fqdn[:-1])
        _type = change.new._type

        existing = {}
        # Find all of the existing CF records for this name & type
        for record in self.zone_records(zone):
            name = zone.hostname_from_fqdn(record['name'])
            # Use the _record_for so that we include all of standard
            # conversion logic
            r = self._record_for(zone, name, record['type'], [record], True)
            if hostname == r.name and _type == r._type:
                # Round trip the single value through a record to contents flow
                # to get a consistent _gen_data result that matches what
                # went in to new_contents
                data = self._gen_data(r).next()

                # Record the record_id and data for this existing record
                key = self._gen_key(data)
                existing[key] = {
                    'record_id': record['id'],
                    'data': data,
                }

        # Build up a list of new CF records for this Update
        new = {
            self._gen_key(d): d for d in self._gen_data(change.new)
        }

        # OK we now have a picture of the old & new CF records, our next step
        # is to figure out which records need to be deleted
        deletes = {}
        for key, info in existing.items():
            if key not in new:
                deletes[key] = info
        # Now we need to figure out which records will need to be created
        creates = {}
        # And which will be updated
        updates = {}
        for key, data in new.items():
            if key in existing:
                # To update we need to combine the new data and existing's
                # record_id. old_data is just for debugging/logging purposes
                old_info = existing[key]
                updates[key] = {
                    'record_id': old_info['record_id'],
                    'data': data,
                    'old_data': old_info['data'],
                }
            else:
                creates[key] = data

        # To do this as safely as possible we'll add new things first, update
        # existing things, and then remove old things. This should (try) and
        # ensure that we have as many value CF records in their system as
        # possible at any given time. Ideally we'd have a "batch" API that
        # would allow create, delete, and upsert style stuff so operations
        # could be done atomically, but that's not available so we made the
        # best of it...

        # However, there are record types like CNAME that can only have a
        # single value. B/c of that our create and then delete approach isn't
        # actually viable. To address this we'll convert as many creates &
        # deletes as we can to updates. This will have a minor upside of
        # resulting in fewer ops and in the case of things like CNAME where
        # there's a single create and delete result in a single update instead.
        create_keys = sorted(creates.keys())
        delete_keys = sorted(deletes.keys())
        for i in range(0, min(len(create_keys), len(delete_keys))):
            create_key = create_keys[i]
            create_data = creates.pop(create_key)
            delete_info = deletes.pop(delete_keys[i])
            updates[create_key] = {
                'record_id': delete_info['record_id'],
                'data': create_data,
                'old_data': delete_info['data'],
            }

        # The sorts ensure a consistent order of operations, they're not
        # otherwise required, just makes things deterministic

        # Creates
        path = '/zones/{}/dns_records'.format(zone_id)
        for _, data in sorted(creates.items()):
            self.log.debug('_apply_Update: creating %s', data)
            self._request('POST', path, data=data)

        # Updates
        for _, info in sorted(updates.items()):
            record_id = info['record_id']
            data = info['data']
            old_data = info['old_data']
            path = '/zones/{}/dns_records/{}'.format(zone_id, record_id)
            self.log.debug('_apply_Update: updating %s, %s -> %s',
                           record_id, data, old_data)
            self._request('PUT', path, data=data)

        # Deletes
        for _, info in sorted(deletes.items()):
            record_id = info['record_id']
            old_data = info['data']
            path = '/zones/{}/dns_records/{}'.format(zone_id, record_id)
            self.log.debug('_apply_Update: removing %s, %s', record_id,
                           old_data)
            self._request('DELETE', path)

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

    def _extra_changes(self, existing, desired, changes):
        extra_changes = []

        existing_records = {r: r for r in existing.records}
        changed_records = {c.record for c in changes}

        for desired_record in desired.records:
            if desired_record not in existing.records:  # Will be created
                continue
            elif desired_record in changed_records:  # Already being updated
                continue

            existing_record = existing_records[desired_record]

            if (self._record_is_proxied(existing_record) !=
                    self._record_is_proxied(desired_record)):
                extra_changes.append(Update(existing_record, desired_record))

        return extra_changes
