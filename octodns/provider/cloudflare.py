#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict
from copy import deepcopy
from logging import getLogger
from requests import Session
from time import sleep
from urllib.parse import urlsplit

from ..record import Record, Update
from . import ProviderException
from .base import BaseProvider


class CloudflareError(ProviderException):
    def __init__(self, data):
        try:
            message = data['errors'][0]['message']
        except (IndexError, KeyError, TypeError):
            message = 'Cloudflare error'
        super(CloudflareError, self).__init__(message)


class CloudflareAuthenticationError(CloudflareError):
    def __init__(self, data):
        CloudflareError.__init__(self, data)


class CloudflareRateLimitError(CloudflareError):
    def __init__(self, data):
        CloudflareError.__init__(self, data)


_PROXIABLE_RECORD_TYPES = {'A', 'AAAA', 'ALIAS', 'CNAME'}


class CloudflareProvider(BaseProvider):
    '''
    Cloudflare DNS provider

    cloudflare:
        class: octodns.provider.cloudflare.CloudflareProvider
        # The api key (required)
        # Your Cloudflare account email address (required)
        email: dns-manager@example.com (optional if using token)
        token: foo
        # Import CDN enabled records as CNAME to {}.cdn.cloudflare.net. Records
        # ending at .cdn.cloudflare.net. will be ignored when this provider is
        # not used as the source and the cdn option is enabled.
        #
        # See: https://support.cloudflare.com/hc/en-us/articles/115000830351
        cdn: false
        # Optional. Default: 4. Number of times to retry if a 429 response
        # is received.
        retry_count: 4
        # Optional. Default: 300. Number of seconds to wait before retrying.
        retry_period: 300
        # Optional. Default: 50. Number of zones per page.
        zones_per_page: 50
        # Optional. Default: 100. Number of dns records per page.
        records_per_page: 100

    Note: The "proxied" flag of "A", "AAAA" and "CNAME" records can be managed
          via the YAML provider like so:
              name:
                octodns:
                  cloudflare:
                    proxied: true
                ttl: 120
                type: A
                value: 1.2.3.4
    '''
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS_WEIGHTED = False
    SUPPORTS = set(('ALIAS', 'A', 'AAAA', 'CAA', 'CNAME', 'LOC', 'MX', 'NS',
                    'PTR', 'SRV', 'SPF', 'TXT', 'URLFWD'))

    MIN_TTL = 120
    TIMEOUT = 15

    def __init__(self, id, email=None, token=None, cdn=False, retry_count=4,
                 retry_period=300, zones_per_page=50, records_per_page=100,
                 *args, **kwargs):
        self.log = getLogger(f'CloudflareProvider[{id}]')
        self.log.debug('__init__: id=%s, email=%s, token=***, cdn=%s', id,
                       email, cdn)
        super(CloudflareProvider, self).__init__(id, *args, **kwargs)

        sess = Session()
        if email and token:
            sess.headers.update({
                'X-Auth-Email': email,
                'X-Auth-Key': token,
            })
        else:
            # https://api.cloudflare.com/#getting-started-requests
            # https://tools.ietf.org/html/rfc6750#section-2.1
            sess.headers.update({
                'Authorization': f'Bearer {token}',
            })
        self.cdn = cdn
        self.retry_count = retry_count
        self.retry_period = retry_period
        self.zones_per_page = zones_per_page
        self.records_per_page = records_per_page
        self._sess = sess

        self._zones = None
        self._zone_records = {}

    def _try_request(self, *args, **kwargs):
        tries = self.retry_count
        while True:  # We'll raise to break after our tries expire
            try:
                return self._request(*args, **kwargs)
            except CloudflareRateLimitError:
                if tries <= 1:
                    raise
                tries -= 1
                self.log.warn('rate limit encountered, pausing '
                              'for %ds and trying again, %d remaining',
                              self.retry_period, tries)
                sleep(self.retry_period)

    def _request(self, method, path, params=None, data=None):
        self.log.debug('_request: method=%s, path=%s', method, path)

        url = f'https://api.cloudflare.com/client/v4{path}'
        resp = self._sess.request(method, url, params=params, json=data,
                                  timeout=self.TIMEOUT)
        self.log.debug('_request:   status=%d', resp.status_code)
        if resp.status_code == 400:
            self.log.debug('_request:   data=%s', data)
            raise CloudflareError(resp.json())
        if resp.status_code == 403:
            raise CloudflareAuthenticationError(resp.json())
        if resp.status_code == 429:
            raise CloudflareRateLimitError(resp.json())

        resp.raise_for_status()
        return resp.json()

    def _change_keyer(self, change):
        key = change.__class__.__name__
        order = {'Delete': 0, 'Create': 1, 'Update': 2}
        return order[key]

    @property
    def zones(self):
        if self._zones is None:
            page = 1
            zones = []
            while page:
                resp = self._try_request('GET', '/zones',
                                         params={
                                                'page': page,
                                                'per_page': self.zones_per_page
                                         })
                zones += resp['result']
                info = resp['result_info']
                if info['count'] > 0 and info['count'] == info['per_page']:
                    page += 1
                else:
                    page = None

            self._zones = {f'{z["name"]}.': z['id'] for z in zones}

        return self._zones

    def _ttl_data(self, ttl):
        return 300 if ttl == 1 else ttl

    def _data_for_cdn(self, name, _type, records):
        self.log.info('CDN rewrite for %s', records[0]['name'])
        _type = "CNAME"
        if name == "":
            _type = "ALIAS"

        return {
            'ttl': self._ttl_data(records[0]['ttl']),
            'type': _type,
            'value': f'{records[0]["name"]}.cdn.cloudflare.net.',
        }

    def _data_for_multiple(self, _type, records):
        return {
            'ttl': self._ttl_data(records[0]['ttl']),
            'type': _type,
            'values': [r['content'] for r in records],
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple
    _data_for_SPF = _data_for_multiple

    def _data_for_TXT(self, _type, records):
        return {
            'ttl': self._ttl_data(records[0]['ttl']),
            'type': _type,
            'values': [r['content'].replace(';', '\\;') for r in records],
        }

    def _data_for_CAA(self, _type, records):
        values = []
        for r in records:
            data = r['data']
            values.append(data)
        return {
            'ttl': self._ttl_data(records[0]['ttl']),
            'type': _type,
            'values': values,
        }

    def _data_for_CNAME(self, _type, records):
        only = records[0]
        return {
            'ttl': self._ttl_data(only['ttl']),
            'type': _type,
            'value': f'{only["content"]}.'
        }

    _data_for_ALIAS = _data_for_CNAME
    _data_for_PTR = _data_for_CNAME

    def _data_for_LOC(self, _type, records):
        values = []
        for record in records:
            r = record['data']
            values.append({
                'lat_degrees': int(r['lat_degrees']),
                'lat_minutes': int(r['lat_minutes']),
                'lat_seconds': float(r['lat_seconds']),
                'lat_direction': r['lat_direction'],
                'long_degrees': int(r['long_degrees']),
                'long_minutes': int(r['long_minutes']),
                'long_seconds': float(r['long_seconds']),
                'long_direction': r['long_direction'],
                'altitude': float(r['altitude']),
                'size': float(r['size']),
                'precision_horz': float(r['precision_horz']),
                'precision_vert': float(r['precision_vert']),
            })
        return {
            'ttl': self._ttl_data(records[0]['ttl']),
            'type': _type,
            'values': values
        }

    def _data_for_MX(self, _type, records):
        values = []
        for r in records:
            values.append({
                'preference': r['priority'],
                'exchange': f'{r["content"]}.',
            })
        return {
            'ttl': self._ttl_data(records[0]['ttl']),
            'type': _type,
            'values': values,
        }

    def _data_for_NS(self, _type, records):
        return {
            'ttl': self._ttl_data(records[0]['ttl']),
            'type': _type,
            'values': [f'{r["content"]}.' for r in records],
        }

    def _data_for_SRV(self, _type, records):
        values = []
        for r in records:
            target = (f'{r["data"]["target"]}.'
                      if r['data']['target'] != "." else ".")
            values.append({
                'priority': r['data']['priority'],
                'weight': r['data']['weight'],
                'port': r['data']['port'],
                'target': target,
            })
        return {
            'type': _type,
            'ttl': self._ttl_data(records[0]['ttl']),
            'values': values
        }

    def _data_for_URLFWD(self, _type, records):
        values = []
        for r in records:
            values.append({
                'path': r['path'],
                'target': r['url'],
                'code': r['status_code'],
                'masking': 2,
                'query': 0,
            })
        return {
            'type': _type,
            'ttl': 300,  # ttl does not exist for this type, forcing a setting
            'values': values
        }

    def zone_records(self, zone):
        if zone.name not in self._zone_records:
            zone_id = self.zones.get(zone.name, False)
            if not zone_id:
                return []

            records = []
            path = f'/zones/{zone_id}/dns_records'
            page = 1
            while page:
                resp = self._try_request('GET', path, params={'page': page,
                                         'per_page': self.records_per_page})
                records += resp['result']
                info = resp['result_info']
                if info['count'] > 0 and info['count'] == info['per_page']:
                    page += 1
                else:
                    page = None

            path = f'/zones/{zone_id}/pagerules'
            resp = self._try_request('GET', path, params={'status': 'active'})
            for r in resp['result']:
                # assumption, base on API guide, will only contain 1 action
                if r['actions'][0]['id'] == 'forwarding_url':
                    records += [r]

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

            data_for = getattr(self, f'_data_for_{_type}')
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
                if 'targets' in record:
                    # assumption, targets will always contain 1 target
                    # API documentation only indicates 'url' as the only target
                    # if record['targets'][0]['target'] == 'url':
                    uri = record['targets'][0]['constraint']['value']
                    uri = '//' + uri if not uri.startswith('http') else uri
                    parsed_uri = urlsplit(uri)
                    name = zone.hostname_from_fqdn(parsed_uri.netloc)
                    path = parsed_uri.path
                    _type = 'URLFWD'
                    # assumption, actions will always contain 1 action
                    _values = record['actions'][0]['value']
                    _values['path'] = path
                    # no ttl set by pagerule, creating one
                    _values['ttl'] = 300
                    values[name][_type].append(_values)
                # the dns_records branch
                # elif 'name' in record:
                else:
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
            elif change.new._type == 'URLFWD':
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

    _contents_for_PTR = _contents_for_CNAME

    def _contents_for_LOC(self, record):
        for value in record.values:
            yield {
                'data': {
                    'lat_degrees': value.lat_degrees,
                    'lat_minutes': value.lat_minutes,
                    'lat_seconds': value.lat_seconds,
                    'lat_direction': value.lat_direction,
                    'long_degrees': value.long_degrees,
                    'long_minutes': value.long_minutes,
                    'long_seconds': value.long_seconds,
                    'long_direction': value.long_direction,
                    'altitude': value.altitude,
                    'size': value.size,
                    'precision_horz': value.precision_horz,
                    'precision_vert': value.precision_vert,
                }
            }

    def _contents_for_MX(self, record):
        for value in record.values:
            yield {
                'priority': value.preference,
                'content': value.exchange
            }

    def _contents_for_SRV(self, record):
        try:
            service, proto, subdomain = record.name.split('.', 2)
            # We have a SRV in a sub-zone
        except ValueError:
            # We have a SRV in the zone
            service, proto = record.name.split('.', 1)
            subdomain = None

        name = record.zone.name
        if subdomain:
            name = subdomain

        for value in record.values:
            target = value.target[:-1] if value.target != "." else "."

            yield {
                'data': {
                    'service': service,
                    'proto': proto,
                    'name': name,
                    'priority': value.priority,
                    'weight': value.weight,
                    'port': value.port,
                    'target': target,
                }
            }

    def _contents_for_URLFWD(self, record):
        name = record.fqdn[:-1]
        for value in record.values:
            yield {
                'targets': [
                    {
                        'target': 'url',
                        'constraint': {
                            'operator': 'matches',
                            'value': name + value.path
                        }
                    }
                ],
                'actions': [
                    {
                        'id': 'forwarding_url',
                        'value': {
                            'url': value.target,
                            'status_code': value.code,
                        }
                    }
                ],
                'status': 'active',
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

        if _type == 'URLFWD':
            contents_for = getattr(self, f'_contents_for_{_type}')
            for content in contents_for(record):
                yield content
        else:
            contents_for = getattr(self, f'_contents_for_{_type}')
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
        # BUT... there are exceptions. MX, CAA, LOC and SRV don't have a simple
        # content as things are currently implemented so we need to handle
        # those explicitly and create unique/hashable strings for them.
        # AND... for URLFWD/Redirects additional adventures are created.
        _type = data.get('type', 'URLFWD')
        if _type == 'MX':
            priority = data['priority']
            content = data['content']
            return f'{priority} {content}'
        elif _type == 'CAA':
            data = data['data']
            flags = data['flags']
            tag = data['tag']
            value = data['value']
            return f'{flags} {tag} {value}'
        elif _type == 'SRV':
            data = data['data']
            port = data['port']
            priority = data['priority']
            target = data['target']
            weight = data['weight']
            return f'{port} {priority} {target} {weight}'
        elif _type == 'LOC':
            data = data['data']
            lat_degrees = data['lat_degrees']
            lat_minutes = data['lat_minutes']
            lat_seconds = data['lat_seconds']
            lat_direction = data['lat_direction']
            long_degrees = data['long_degrees']
            long_minutes = data['long_minutes']
            long_seconds = data['long_seconds']
            long_direction = data['long_direction']
            altitude = data['altitude']
            size = data['size']
            precision_horz = data['precision_horz']
            precision_vert = data['precision_vert']
            return f'{lat_degrees} {lat_minutes} {lat_seconds} ' \
                f'{lat_direction} {long_degrees} {long_minutes} ' \
                f'{long_seconds} {long_direction} {altitude} {size} ' \
                f'{precision_horz} {precision_vert}'
        elif _type == 'URLFWD':
            uri = data['targets'][0]['constraint']['value']
            uri = '//' + uri if not uri.startswith('http') else uri
            parsed_uri = urlsplit(uri)
            url = data['actions'][0]['value']['url']
            status_code = data['actions'][0]['value']['status_code']
            return f'{parsed_uri.netloc} {parsed_uri.path} {url} ' + \
                f'{status_code}'

        return data['content']

    def _apply_Create(self, change):
        new = change.new
        zone_id = self.zones[new.zone.name]
        if new._type == 'URLFWD':
            path = f'/zones/{zone_id}/pagerules'
        else:
            path = f'/zones/{zone_id}/dns_records'
        for content in self._gen_data(new):
            self._try_request('POST', path, data=content)

    def _apply_Update(self, change):
        zone = change.new.zone
        zone_id = self.zones[zone.name]
        hostname = zone.hostname_from_fqdn(change.new.fqdn[:-1])
        _type = change.new._type

        existing = {}
        # Find all of the existing CF records for this name & type
        for record in self.zone_records(zone):
            if 'targets' in record:
                uri = record['targets'][0]['constraint']['value']
                uri = '//' + uri if not uri.startswith('http') else uri
                parsed_uri = urlsplit(uri)
                name = zone.hostname_from_fqdn(parsed_uri.netloc)
                path = parsed_uri.path
                # assumption, actions will always contain 1 action
                _values = record['actions'][0]['value']
                _values['path'] = path
                _values['ttl'] = 300
                _values['type'] = 'URLFWD'
                record.update(_values)
            else:
                name = zone.hostname_from_fqdn(record['name'])
            # Use the _record_for so that we include all of standard
            # conversion logic
            r = self._record_for(zone, name, record['type'], [record], True)
            if hostname == r.name and _type == r._type:
                # Round trip the single value through a record to contents
                # flow to get a consistent _gen_data result that matches
                # what went in to new_contents
                data = next(self._gen_data(r))

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
        if _type == 'URLFWD':
            path = f'/zones/{zone_id}/pagerules'
        else:
            path = f'/zones/{zone_id}/dns_records'
        for _, data in sorted(creates.items()):
            self.log.debug('_apply_Update: creating %s', data)
            self._try_request('POST', path, data=data)

        # Updates
        for _, info in sorted(updates.items()):
            record_id = info['record_id']
            data = info['data']
            old_data = info['old_data']
            if _type == 'URLFWD':
                path = f'/zones/{zone_id}/pagerules/{record_id}'
            else:
                path = f'/zones/{zone_id}/dns_records/{record_id}'
            self.log.debug('_apply_Update: updating %s, %s -> %s',
                           record_id, data, old_data)
            self._try_request('PUT', path, data=data)

        # Deletes
        for _, info in sorted(deletes.items()):
            record_id = info['record_id']
            old_data = info['data']
            if _type == 'URLFWD':
                path = f'/zones/{zone_id}/pagerules/{record_id}'
            else:
                path = f'/zones/{zone_id}/dns_records/{record_id}'
            self.log.debug('_apply_Update: removing %s, %s', record_id,
                           old_data)
            self._try_request('DELETE', path)

    def _apply_Delete(self, change):
        existing = change.existing
        existing_name = existing.fqdn[:-1]
        # Make sure to map ALIAS to CNAME when looking for the target to delete
        existing_type = 'CNAME' if existing._type == 'ALIAS' \
            else existing._type
        for record in self.zone_records(existing.zone):
            if 'targets' in record:
                uri = record['targets'][0]['constraint']['value']
                uri = '//' + uri if not uri.startswith('http') else uri
                parsed_uri = urlsplit(uri)
                record_name = parsed_uri.netloc
                record_type = 'URLFWD'
                zone_id = self.zones.get(existing.zone.name, False)
                if existing_name == record_name and \
                   existing_type == record_type:
                    path = f'/zones/{zone_id}/pagerules/{record["id"]}'
                    self._try_request('DELETE', path)
            else:
                if existing_name == record['name'] and \
                   existing_type == record['type']:
                    path = f'/zones/{record["zone_id"]}/dns_records/' \
                        f'{record["id"]}'
                    self._try_request('DELETE', path)

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
            resp = self._try_request('POST', '/zones', data=data)
            zone_id = resp['result']['id']
            self.zones[name] = zone_id
            self._zone_records[name] = {}

        # Force the operation order to be Delete() -> Create() -> Update()
        # This will help avoid problems in updating a CNAME record into an
        # A record and vice-versa
        changes.sort(key=self._change_keyer)

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, f'_apply_{class_name}')(change)

        # clear the cache
        self._zone_records.pop(name, None)

    def _extra_changes(self, existing, desired, changes):
        extra_changes = []

        existing_records = {r: r for r in existing.records}
        changed_records = {c.record for c in changes}

        for desired_record in desired.records:
            existing_record = existing_records.get(desired_record, None)
            if not existing_record:  # Will be created
                continue
            elif desired_record in changed_records:  # Already being updated
                continue

            if (self._record_is_proxied(existing_record) !=
                    self._record_is_proxied(desired_record)):
                extra_changes.append(Update(existing_record, desired_record))

        return extra_changes
