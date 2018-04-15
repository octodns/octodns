#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict
from logging import getLogger
from json import dumps
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

        return Record.new(zone, name, data, source=self, lenient=lenient)

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

                    zone.add_record(record)

        self.log.info('populate:   found %s records, exists=%s',
                      len(zone.records) - before, exists)
        return exists

    def _include_change(self, change):
        if isinstance(change, Update):
            existing = change.existing.data
            new = change.new.data
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

    def _gen_contents(self, record):
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
            yield content

    def _apply_Create(self, change):
        new = change.new
        zone_id = self.zones[new.zone.name]
        path = '/zones/{}/dns_records'.format(zone_id)
        for content in self._gen_contents(new):
            self._request('POST', path, data=content)

    def _hash_content(self, content):
        # Some of the dicts are nested so this seems about as good as any
        # option we have for consistently hashing them (within a single run)
        return hash(dumps(content, sort_keys=True))

    def _apply_Update(self, change):

        # Ugh, this is pretty complicated and ugly, mainly due to the
        # sub-optimal API/semantics. Ideally we'd have a batch change API like
        # Route53's to make this 100% clean and safe without all this PITA, but
        # we don't so we'll have to work around that and manually do it as
        # safely as possible. Note this still isn't perfect as we don't/can't
        # practically take into account things like the different "types" of
        # CAA records so when we "swap" there may be brief periods where things
        # are invalid or even worse Cloudflare may update their validations to
        # prevent dups. I see no clean way around that short of making this
        # understand 100% of the details of each record type and develop an
        # individual/specific ordering of changes that prevents it. That'd
        # probably result in more code than this whole provider currently has
        # so... :-(

        existing_contents = {
            self._hash_content(c): c
            for c in self._gen_contents(change.existing)
        }
        new_contents = {
            self._hash_content(c): c
            for c in self._gen_contents(change.new)
        }

        # Find the things we need to add
        adds = []
        for k, content in new_contents.items():
            try:
                existing_contents.pop(k)
                self.log.debug('_apply_Update: leaving %s', content)
            except KeyError:
                adds.append(content)

        zone = change.new.zone
        zone_id = self.zones[zone.name]

        # Find things we need to remove
        hostname = zone.hostname_from_fqdn(change.new.fqdn[:-1])
        _type = change.new._type
        # OK, work through each record from the zone
        for record in self.zone_records(zone):
            name = zone.hostname_from_fqdn(record['name'])
            # Use the _record_for so that we include all of standard
            # conversion logic
            r = self._record_for(zone, name, record['type'], [record], True)
            if hostname == r.name and _type == r._type:

                # Round trip the single value through a record to contents flow
                # to get a consistent _gen_contents result that matches what
                # went in to new_contents
                content = self._gen_contents(r).next()

                # If the hash of that dict isn't in new this record isn't
                # needed
                if self._hash_content(content) not in new_contents:
                    rid = record['id']
                    path = '/zones/{}/dns_records/{}'.format(record['zone_id'],
                                                             rid)
                    try:
                        add_content = adds.pop(0)
                        self.log.debug('_apply_Update: swapping %s -> %s, %s',
                                       content, add_content, rid)
                        self._request('PUT', path, data=add_content)
                    except IndexError:
                        self.log.debug('_apply_Update: removing %s, %s',
                                       content, rid)
                        self._request('DELETE', path)

        # Any remaining adds just need to be created
        path = '/zones/{}/dns_records'.format(zone_id)
        for content in adds:
            self.log.debug('_apply_Update: adding %s', content)
            self._request('POST', path, data=content)

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
