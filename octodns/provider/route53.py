#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from boto3 import client
from botocore.config import Config
from collections import defaultdict
from incf.countryutils.transformations import cca_to_ctca2
from uuid import uuid4
import logging
import re

from ..record import Record, Update
from .base import BaseProvider


octal_re = re.compile(r'\\(\d\d\d)')


def _octal_replace(s):
    # See http://docs.aws.amazon.com/Route53/latest/DeveloperGuide/
    #     DomainNameFormat.html
    return octal_re.sub(lambda m: chr(int(m.group(1), 8)), s)


class _Route53Record(object):

    @classmethod
    def new(self, provider, record, creating):
        ret = set()
        if getattr(record, 'geo', False):
            ret.add(_Route53GeoDefault(provider, record, creating))
            for ident, geo in record.geo.items():
                ret.add(_Route53GeoRecord(provider, record, ident, geo,
                                          creating))
        else:
            ret.add(_Route53Record(provider, record, creating))
        return ret

    def __init__(self, provider, record, creating):
        self.fqdn = record.fqdn
        self._type = record._type
        self.ttl = record.ttl

        values_for = getattr(self, '_values_for_{}'.format(self._type))
        self.values = values_for(record)

    def mod(self, action):
        return {
            'Action': action,
            'ResourceRecordSet': {
                'Name': self.fqdn,
                'ResourceRecords': [{'Value': v} for v in self.values],
                'TTL': self.ttl,
                'Type': self._type,
            }
        }

    # NOTE: we're using __hash__ and __cmp__ methods that consider
    # _Route53Records equivalent if they have the same class, fqdn, and _type.
    # Values are ignored. This is useful when computing diffs/changes.

    def __hash__(self):
        'sub-classes should never use this method'
        return '{}:{}'.format(self.fqdn, self._type).__hash__()

    def __cmp__(self, other):
        '''sub-classes should call up to this and return its value if non-zero.
        When it's zero they should compute their own __cmp__'''
        if self.__class__ != other.__class__:
            return cmp(self.__class__, other.__class__)
        elif self.fqdn != other.fqdn:
            return cmp(self.fqdn, other.fqdn)
        elif self._type != other._type:
            return cmp(self._type, other._type)
        # We're ignoring ttl, it's not an actual differentiator
        return 0

    def __repr__(self):
        return '_Route53Record<{} {} {} {}>'.format(self.fqdn, self._type,
                                                    self.ttl, self.values)

    def _values_for_values(self, record):
        return record.values

    _values_for_A = _values_for_values
    _values_for_AAAA = _values_for_values
    _values_for_NS = _values_for_values

    def _values_for_CAA(self, record):
        return ['{} {} "{}"'.format(v.flags, v.tag, v.value)
                for v in record.values]

    def _values_for_value(self, record):
        return [record.value]

    _values_for_CNAME = _values_for_value
    _values_for_PTR = _values_for_value

    def _values_for_MX(self, record):
        return ['{} {}'.format(v.preference, v.exchange)
                for v in record.values]

    def _values_for_NAPTR(self, record):
        return ['{} {} "{}" "{}" "{}" {}'
                .format(v.order, v.preference,
                        v.flags if v.flags else '',
                        v.service if v.service else '',
                        v.regexp if v.regexp else '',
                        v.replacement)
                for v in record.values]

    def _values_for_quoted(self, record):
        return record.chunked_values

    _values_for_SPF = _values_for_quoted
    _values_for_TXT = _values_for_quoted

    def _values_for_SRV(self, record):
        return ['{} {} {} {}'.format(v.priority, v.weight, v.port,
                                     v.target)
                for v in record.values]


class _Route53GeoDefault(_Route53Record):

    def mod(self, action):
        return {
            'Action': action,
            'ResourceRecordSet': {
                'Name': self.fqdn,
                'GeoLocation': {
                    'CountryCode': '*'
                },
                'ResourceRecords': [{'Value': v} for v in self.values],
                'SetIdentifier': 'default',
                'TTL': self.ttl,
                'Type': self._type,
            }
        }

    def __hash__(self):
        return '{}:{}:default'.format(self.fqdn, self._type).__hash__()

    def __repr__(self):
        return '_Route53GeoDefault<{} {} {} {}>'.format(self.fqdn, self._type,
                                                        self.ttl, self.values)


class _Route53GeoRecord(_Route53Record):

    def __init__(self, provider, record, ident, geo, creating):
        super(_Route53GeoRecord, self).__init__(provider, record, creating)
        self.geo = geo

        self.health_check_id = provider.get_health_check_id(record, ident,
                                                            geo, creating)

    def mod(self, action):
        geo = self.geo
        rrset = {
            'Name': self.fqdn,
            'GeoLocation': {
                'CountryCode': '*'
            },
            'ResourceRecords': [{'Value': v} for v in geo.values],
            'SetIdentifier': geo.code,
            'TTL': self.ttl,
            'Type': self._type,
        }

        if self.health_check_id:
            rrset['HealthCheckId'] = self.health_check_id

        if geo.subdivision_code:
            rrset['GeoLocation'] = {
                'CountryCode': geo.country_code,
                'SubdivisionCode': geo.subdivision_code
            }
        elif geo.country_code:
            rrset['GeoLocation'] = {
                'CountryCode': geo.country_code
            }
        else:
            rrset['GeoLocation'] = {
                'ContinentCode': geo.continent_code
            }

        return {
            'Action': action,
            'ResourceRecordSet': rrset,
        }

    def __hash__(self):
        return '{}:{}:{}'.format(self.fqdn, self._type,
                                 self.geo.code).__hash__()

    def __cmp__(self, other):
        ret = super(_Route53GeoRecord, self).__cmp__(other)
        if ret != 0:
            return ret
        return cmp(self.geo.code, other.geo.code)

    def __repr__(self):
        return '_Route53GeoRecord<{} {} {} {} {}>'.format(self.fqdn,
                                                          self._type, self.ttl,
                                                          self.geo.code,
                                                          self.values)


class Route53Provider(BaseProvider):
    '''
    AWS Route53 Provider

    route53:
        class: octodns.provider.route53.Route53Provider
        # The AWS access key id (required)
        access_key_id:
        # The AWS secret access key (required)
        secret_access_key:

    In general the account used will need full permissions on Route53.
    '''
    SUPPORTS_GEO = True
    SUPPORTS = set(('A', 'AAAA', 'CAA', 'CNAME', 'MX', 'NAPTR', 'NS', 'PTR',
                    'SPF', 'SRV', 'TXT'))

    # This should be bumped when there are underlying changes made to the
    # health check config.
    HEALTH_CHECK_VERSION = '0001'

    def __init__(self, id, access_key_id, secret_access_key, max_changes=1000,
                 client_max_attempts=None, *args, **kwargs):
        self.max_changes = max_changes
        self.log = logging.getLogger('Route53Provider[{}]'.format(id))
        self.log.debug('__init__: id=%s, access_key_id=%s, '
                       'secret_access_key=***', id, access_key_id)
        super(Route53Provider, self).__init__(id, *args, **kwargs)

        config = None
        if client_max_attempts is not None:
            self.log.info('__init__: setting max_attempts to %d',
                          client_max_attempts)
            config = Config(retries={'max_attempts': client_max_attempts})

        self._conn = client('route53', aws_access_key_id=access_key_id,
                            aws_secret_access_key=secret_access_key,
                            config=config)

        self._r53_zones = None
        self._r53_rrsets = {}
        self._health_checks = None

    @property
    def r53_zones(self):
        if self._r53_zones is None:
            self.log.debug('r53_zones: loading')
            zones = {}
            more = True
            start = {}
            while more:
                resp = self._conn.list_hosted_zones(**start)
                for z in resp['HostedZones']:
                    zones[z['Name']] = z['Id']
                more = resp['IsTruncated']
                start['Marker'] = resp.get('NextMarker', None)

            self._r53_zones = zones

        return self._r53_zones

    def _get_zone_id(self, name, create=False):
        self.log.debug('_get_zone_id: name=%s', name)
        if name in self.r53_zones:
            id = self.r53_zones[name]
            self.log.debug('_get_zone_id:   id=%s', id)
            return id
        if create:
            ref = uuid4().hex
            self.log.debug('_get_zone_id:   no matching zone, creating, '
                           'ref=%s', ref)
            resp = self._conn.create_hosted_zone(Name=name,
                                                 CallerReference=ref)
            self.r53_zones[name] = id = resp['HostedZone']['Id']
            return id
        return None

    def _parse_geo(self, rrset):
        try:
            loc = rrset['GeoLocation']
        except KeyError:
            # No geo loc
            return
        try:
            return loc['ContinentCode']
        except KeyError:
            # Must be country
            cc = loc['CountryCode']
            if cc == '*':
                # This is the default
                return
            cn = cca_to_ctca2(cc)
            try:
                return '{}-{}-{}'.format(cn, cc, loc['SubdivisionCode'])
            except KeyError:
                return '{}-{}'.format(cn, cc)

    def _data_for_geo(self, rrset):
        ret = {
            'type': rrset['Type'],
            'values': [v['Value'] for v in rrset['ResourceRecords']],
            'ttl': int(rrset['TTL'])
        }
        geo = self._parse_geo(rrset)
        if geo:
            ret['geo'] = geo
        return ret

    _data_for_A = _data_for_geo
    _data_for_AAAA = _data_for_geo

    def _data_for_CAA(self, rrset):
        values = []
        for rr in rrset['ResourceRecords']:
            flags, tag, value = rr['Value'].split(' ')
            values.append({
                'flags': flags,
                'tag': tag,
                'value': value[1:-1],
            })
        return {
            'type': rrset['Type'],
            'values': values,
            'ttl': int(rrset['TTL'])
        }

    def _data_for_single(self, rrset):
        return {
            'type': rrset['Type'],
            'value': rrset['ResourceRecords'][0]['Value'],
            'ttl': int(rrset['TTL'])
        }

    _data_for_PTR = _data_for_single
    _data_for_CNAME = _data_for_single

    _fix_semicolons = re.compile(r'(?<!\\);')

    def _data_for_quoted(self, rrset):
        return {
            'type': rrset['Type'],
            'values': [self._fix_semicolons.sub('\\;', rr['Value'][1:-1])
                       for rr in rrset['ResourceRecords']],
            'ttl': int(rrset['TTL'])
        }

    _data_for_TXT = _data_for_quoted
    _data_for_SPF = _data_for_quoted

    def _data_for_MX(self, rrset):
        values = []
        for rr in rrset['ResourceRecords']:
            preference, exchange = rr['Value'].split(' ')
            values.append({
                'preference': preference,
                'exchange': exchange,
            })
        return {
            'type': rrset['Type'],
            'values': values,
            'ttl': int(rrset['TTL'])
        }

    def _data_for_NAPTR(self, rrset):
        values = []
        for rr in rrset['ResourceRecords']:
            order, preference, flags, service, regexp, replacement = \
                rr['Value'].split(' ')
            flags = flags[1:-1]
            service = service[1:-1]
            regexp = regexp[1:-1]
            values.append({
                'order': order,
                'preference': preference,
                'flags': flags,
                'service': service,
                'regexp': regexp,
                'replacement': replacement,
            })
        return {
            'type': rrset['Type'],
            'values': values,
            'ttl': int(rrset['TTL'])
        }

    def _data_for_NS(self, rrset):
        return {
            'type': rrset['Type'],
            'values': [v['Value'] for v in rrset['ResourceRecords']],
            'ttl': int(rrset['TTL'])
        }

    def _data_for_SRV(self, rrset):
        values = []
        for rr in rrset['ResourceRecords']:
            priority, weight, port, target = rr['Value'].split(' ')
            values.append({
                'priority': priority,
                'weight': weight,
                'port': port,
                'target': target,
            })
        return {
            'type': rrset['Type'],
            'values': values,
            'ttl': int(rrset['TTL'])
        }

    def _load_records(self, zone_id):
        if zone_id not in self._r53_rrsets:
            self.log.debug('_load_records: zone_id=%s loading', zone_id)
            rrsets = []
            more = True
            start = {}
            while more:
                resp = \
                    self._conn.list_resource_record_sets(HostedZoneId=zone_id,
                                                         **start)
                rrsets += resp['ResourceRecordSets']
                more = resp['IsTruncated']
                if more:
                    start = {
                        'StartRecordName': resp['NextRecordName'],
                        'StartRecordType': resp['NextRecordType'],
                    }
                    try:
                        start['StartRecordIdentifier'] = \
                            resp['NextRecordIdentifier']
                    except KeyError:
                        pass

            self._r53_rrsets[zone_id] = rrsets

        return self._r53_rrsets[zone_id]

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        before = len(zone.records)
        exists = False

        zone_id = self._get_zone_id(zone.name)
        if zone_id:
            exists = True
            records = defaultdict(lambda: defaultdict(list))
            for rrset in self._load_records(zone_id):
                record_name = zone.hostname_from_fqdn(rrset['Name'])
                record_name = _octal_replace(record_name)
                record_type = rrset['Type']
                if record_type not in self.SUPPORTS:
                    continue
                if 'AliasTarget' in rrset:
                    # Alias records are Route53 specific and are not
                    # portable, so we need to skip them
                    self.log.warning("%s is an Alias record. Skipping..."
                                     % rrset['Name'])
                    continue
                data = getattr(self, '_data_for_{}'.format(record_type))(rrset)
                records[record_name][record_type].append(data)

            for name, types in records.items():
                for _type, data in types.items():
                    if len(data) > 1:
                        # Multiple data indicates a record with GeoDNS, convert
                        # them data into the format we need
                        geo = {}
                        for d in data:
                            try:
                                geo[d['geo']] = d['values']
                            except KeyError:
                                primary = d
                        data = primary
                        data['geo'] = geo
                    else:
                        data = data[0]
                    record = Record.new(zone, name, data, source=self,
                                        lenient=lenient)
                    zone.add_record(record)

        self.log.info('populate:   found %s records, exists=%s',
                      len(zone.records) - before, exists)
        return exists

    def _gen_mods(self, action, records):
        '''
        Turns `_Route53*`s in to `change_resource_record_sets` `Changes`
        '''
        return [r.mod(action) for r in records]

    @property
    def health_checks(self):
        if self._health_checks is None:
            # need to do the first load
            self.log.debug('health_checks: loading')
            checks = {}
            more = True
            start = {}
            while more:
                resp = self._conn.list_health_checks(**start)
                for health_check in resp['HealthChecks']:
                    # our format for CallerReference is dddd:hex-uuid
                    ref = health_check.get('CallerReference', 'xxxxx')
                    if len(ref) > 4 and ref[4] != ':':
                        # ignore anything else
                        continue
                    checks[health_check['Id']] = health_check
                more = resp['IsTruncated']
                start['Marker'] = resp.get('NextMarker', None)

            self._health_checks = checks

        # We've got a cached version use it
        return self._health_checks

    def _health_check_equivilent(self, host, path, protocol, port,
                                 health_check, first_value=None):
        config = health_check['HealthCheckConfig']
        return host == config['FullyQualifiedDomainName'] and \
            path == config['ResourcePath'] and protocol == config['Type'] \
            and port == config['Port'] and \
            (first_value is None or first_value == config['IPAddress'])

    def get_health_check_id(self, record, ident, geo, create):
        # fqdn & the first value are special, we use them to match up health
        # checks to their records. Route53 health checks check a single ip and
        # we're going to assume that ips are interchangeable to avoid
        # health-checking each one independently
        fqdn = record.fqdn
        first_value = geo.values[0]
        self.log.debug('get_health_check_id: fqdn=%s, type=%s, geo=%s, '
                       'first_value=%s', fqdn, record._type, ident,
                       first_value)

        healthcheck_host = record.healthcheck_host
        healthcheck_path = record.healthcheck_path
        healthcheck_protocol = record.healthcheck_protocol
        healthcheck_port = record.healthcheck_port

        # we're looking for a healthcheck with the current version & our record
        # type, we'll ignore anything else
        expected_ref = '{}:{}:{}:'.format(self.HEALTH_CHECK_VERSION,
                                          record._type, record.fqdn)
        for id, health_check in self.health_checks.items():
            if not health_check['CallerReference'].startswith(expected_ref):
                # not match, ignore
                continue
            if self._health_check_equivilent(healthcheck_host,
                                             healthcheck_path,
                                             healthcheck_protocol,
                                             healthcheck_port, health_check,
                                             first_value=first_value):
                # this is the health check we're looking for
                self.log.debug('get_health_check_id:   found match id=%s', id)
                return id

        if not create:
            # no existing matches and not allowed to create, return none
            self.log.debug('get_health_check_id:   no matches, no create')
            return

        # no existing matches, we need to create a new health check
        config = {
            'EnableSNI': healthcheck_protocol == 'HTTPS',
            'FailureThreshold': 6,
            'FullyQualifiedDomainName': healthcheck_host,
            'IPAddress': first_value,
            'MeasureLatency': True,
            'Port': healthcheck_port,
            'RequestInterval': 10,
            'ResourcePath': healthcheck_path,
            'Type': healthcheck_protocol,
        }
        ref = '{}:{}:{}:{}'.format(self.HEALTH_CHECK_VERSION, record._type,
                                   record.fqdn, uuid4().hex[:12])
        resp = self._conn.create_health_check(CallerReference=ref,
                                              HealthCheckConfig=config)
        health_check = resp['HealthCheck']
        id = health_check['Id']
        # store the new health check so that we'll be able to find it in the
        # future
        self._health_checks[id] = health_check
        self.log.info('get_health_check_id: created id=%s, host=%s, path=%s, '
                      'protocol=%s, port=%d, first_value=%s', id,
                      healthcheck_host, healthcheck_path, healthcheck_protocol,
                      healthcheck_port, first_value)
        return id

    def _gc_health_checks(self, record, new):
        if record._type not in ('A', 'AAAA'):
            return
        self.log.debug('_gc_health_checks: record=%s', record)
        # Find the health checks we're using for the new route53 records
        in_use = set()
        for r in new:
            hc_id = getattr(r, 'health_check_id', False)
            if hc_id:
                in_use.add(hc_id)
        self.log.debug('_gc_health_checks:   in_use=%s', in_use)
        # Now we need to run through ALL the health checks looking for those
        # that apply to this record, deleting any that do and are no longer in
        # use
        expected_re = re.compile(r'^\d\d\d\d:{}:{}:'
                                 .format(record._type, record.fqdn))
        # UNITL 1.0: we'll clean out the previous version of Route53 health
        # checks as best as we can.
        expected_legacy_host = record.fqdn[:-1]
        expected_legacy = '0000:{}:'.format(record._type)
        for id, health_check in self.health_checks.items():
            ref = health_check['CallerReference']
            if expected_re.match(ref) and id not in in_use:
                # this is a health check for this record, but not one we're
                # planning to use going forward
                self.log.info('_gc_health_checks:   deleting id=%s', id)
                self._conn.delete_health_check(HealthCheckId=id)
            elif ref.startswith(expected_legacy):
                config = health_check['HealthCheckConfig']
                if expected_legacy_host == config['FullyQualifiedDomainName']:
                    self.log.info('_gc_health_checks:   deleting legacy id=%s',
                                  id)
                    self._conn.delete_health_check(HealthCheckId=id)

    def _gen_records(self, record, creating=False):
        '''
        Turns an octodns.Record into one or more `_Route53*`s
        '''
        return _Route53Record.new(self, record, creating)

    def _mod_Create(self, change):
        # New is the stuff that needs to be created
        new_records = self._gen_records(change.new, creating=True)
        # Now is a good time to clear out any unused health checks since we
        # know what we'll be using going forward
        self._gc_health_checks(change.new, new_records)
        return self._gen_mods('CREATE', new_records)

    def _mod_Update(self, change):
        # See comments in _Route53Record for how the set math is made to do our
        # bidding here.
        existing_records = self._gen_records(change.existing, creating=False)
        new_records = self._gen_records(change.new, creating=True)
        # Now is a good time to clear out any unused health checks since we
        # know what we'll be using going forward
        self._gc_health_checks(change.new, new_records)
        # Things in existing, but not new are deletes
        deletes = existing_records - new_records
        # Things in new, but not existing are the creates
        creates = new_records - existing_records
        # Things in both need updating, we could optimize this and filter out
        # things that haven't actually changed, but that's for another day.
        # We can't use set math here b/c we won't be able to control which of
        # the two objects will be in the result and we need to ensure it's the
        # new one.
        upserts = set()
        for new_record in new_records:
            if new_record in existing_records:
                upserts.add(new_record)

        return self._gen_mods('DELETE', deletes) + \
            self._gen_mods('CREATE', creates) + \
            self._gen_mods('UPSERT', upserts)

    def _mod_Delete(self, change):
        # Existing is the thing that needs to be deleted
        existing_records = self._gen_records(change.existing, creating=False)
        # Now is a good time to clear out all the health checks since we know
        # we're done with them
        self._gc_health_checks(change.existing, [])
        return self._gen_mods('DELETE', existing_records)

    def _extra_changes(self, desired, changes, **kwargs):
        self.log.debug('_extra_changes: desired=%s', desired.name)
        zone_id = self._get_zone_id(desired.name)
        if not zone_id:
            # zone doesn't exist so no extras to worry about
            return []
        # we'll skip extra checking for anything we're already going to change
        changed = set([c.record for c in changes])
        # ok, now it's time for the reason we're here, we need to go over all
        # the desired records
        extra = []
        for record in desired.records:
            if record in changed:
                # already have a change for it, skipping
                continue
            if not getattr(record, 'geo', False):
                # record doesn't support geo, we don't need to inspect it
                continue
            # OK this is a record we don't have change for that does have geo
            # information. We need to look and see if it needs to be updated
            # b/c of a health check version bump
            self.log.debug('_extra_changes:   inspecting=%s, %s', record.fqdn,
                           record._type)

            healthcheck_host = record.healthcheck_host
            healthcheck_path = record.healthcheck_path
            healthcheck_protocol = record.healthcheck_protocol
            healthcheck_port = record.healthcheck_port
            fqdn = record.fqdn

            # loop through all the r53 rrsets
            for rrset in self._load_records(zone_id):
                if fqdn != rrset['Name'] or record._type != rrset['Type']:
                    # not a name and type match
                    continue
                if rrset.get('GeoLocation', {}) \
                   .get('CountryCode', False) == '*':
                    # it's a default record
                    continue
                # we expect a healthcheck now
                try:
                    health_check_id = rrset['HealthCheckId']
                    health_check = self.health_checks[health_check_id]
                    caller_ref = health_check['CallerReference']
                    if caller_ref.startswith(self.HEALTH_CHECK_VERSION):
                        if self._health_check_equivilent(healthcheck_host,
                                                         healthcheck_path,
                                                         healthcheck_protocol,
                                                         healthcheck_port,
                                                         health_check):
                            # it has the right health check
                            continue
                except (IndexError, KeyError):
                    # no health check id or one that isn't the right version
                    pass
                # no good, doesn't have the right health check, needs an update
                self.log.info('_extra_changes:     health-check caused '
                              'update of %s:%s', record.fqdn, record._type)
                extra.append(Update(record, record))
                # We don't need to process this record any longer
                break

        return extra

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.info('_apply: zone=%s, len(changes)=%d', desired.name,
                      len(changes))

        batch = []
        batch_rs_count = 0
        zone_id = self._get_zone_id(desired.name, True)
        for c in changes:
            mods = getattr(self, '_mod_{}'.format(c.__class__.__name__))(c)
            mods_rs_count = sum(
                [len(m['ResourceRecordSet']['ResourceRecords']) for m in mods]
            )

            if mods_rs_count > self.max_changes:
                # a single mod resulted in too many ResourceRecords changes
                raise Exception('Too many modifications: {}'
                                .format(mods_rs_count))

            # r53 limits changesets to 1000 entries
            if (batch_rs_count + mods_rs_count) < self.max_changes:
                # append to the batch
                batch += mods
                batch_rs_count += mods_rs_count
            else:
                self.log.info('_apply:   sending change request for batch of '
                              '%d mods, %d ResourceRecords', len(batch),
                              batch_rs_count)
                # send the batch
                self._really_apply(batch, zone_id)
                # start a new batch with the leftovers
                batch = mods
                batch_rs_count = mods_rs_count

        # the way the above process works there will always be something left
        # over in batch to process. In the case that we submit a batch up there
        # it was always the case that there was something pushing us over
        # max_changes and thus left over to submit.
        self.log.info('_apply:   sending change request for batch of %d mods,'
                      ' %d ResourceRecords', len(batch),
                      batch_rs_count)
        self._really_apply(batch, zone_id)

    def _really_apply(self, batch, zone_id):
        uuid = uuid4().hex
        batch = {
            'Comment': 'Change: {}'.format(uuid),
            'Changes': batch,
        }
        self.log.debug('_really_apply:   sending change request, comment=%s',
                       batch['Comment'])
        resp = self._conn.change_resource_record_sets(
            HostedZoneId=zone_id, ChangeBatch=batch)
        self.log.debug('_really_apply:   change info=%s', resp['ChangeInfo'])
