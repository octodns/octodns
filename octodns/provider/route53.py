#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from boto3 import client
from collections import defaultdict
from incf.countryutils.transformations import cca_to_ctca2
from uuid import uuid4
import logging
import re

from ..record import Record, Update
from .base import BaseProvider


class _Route53Record(object):

    def __init__(self, fqdn, _type, ttl, record=None, values=None, geo=None,
                 health_check_id=None):
        self.fqdn = fqdn
        self._type = _type
        self.ttl = ttl
        # From here on things are a little ugly, it works, but would be nice to
        # clean up someday.
        if record:
            values_for = getattr(self, '_values_for_{}'.format(self._type))
            self.values = values_for(record)
        else:
            self.values = values
        self.geo = geo
        self.health_check_id = health_check_id
        self.is_geo_default = False

    @property
    def _geo_code(self):
        return getattr(self.geo, 'code', '')

    def _values_for_values(self, record):
        return record.values

    _values_for_A = _values_for_values
    _values_for_AAAA = _values_for_values
    _values_for_NS = _values_for_values

    def _values_for_value(self, record):
        return [record.value]

    _values_for_CNAME = _values_for_value
    _values_for_PTR = _values_for_value

    def _values_for_MX(self, record):
        return ['{} {}'.format(v.priority, v.value) for v in record.values]

    def _values_for_NAPTR(self, record):
        return ['{} {} "{}" "{}" "{}" {}'
                .format(v.order, v.preference,
                        v.flags if v.flags else '',
                        v.service if v.service else '',
                        v.regexp if v.regexp else '',
                        v.replacement)
                for v in record.values]

    def _values_for_quoted(self, record):
        return ['"{}"'.format(v.replace('"', '\\"'))
                for v in record.values]

    _values_for_SPF = _values_for_quoted
    _values_for_TXT = _values_for_quoted

    def _values_for_SRV(self, record):
        return ['{} {} {} {}'.format(v.priority, v.weight, v.port,
                                     v.target)
                for v in record.values]

    def mod(self, action):
        rrset = {
            'Name': self.fqdn,
            'Type': self._type,
            'TTL': self.ttl,
            'ResourceRecords': [{'Value': v} for v in self.values],
        }
        if self.is_geo_default:
            rrset['GeoLocation'] = {
                'CountryCode': '*'
            }
            rrset['SetIdentifier'] = 'default'
        elif self.geo:
            geo = self.geo
            rrset['SetIdentifier'] = geo.code
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

    # NOTE: we're using __hash__ and __cmp__ methods that consider
    # _Route53Records equivalent if they have the same fqdn, _type, and
    # geo.ident. Values are ignored. This is usful when computing
    # diffs/changes.

    def __hash__(self):
        return '{}:{}:{}'.format(self.fqdn, self._type,
                                 self._geo_code).__hash__()

    def __cmp__(self, other):
        return 0 if (self.fqdn == other.fqdn and
                     self._type == other._type and
                     self._geo_code == other._geo_code) else 1

    def __repr__(self):
        return '_Route53Record<{} {:>5} {:8} {}>' \
            .format(self.fqdn, self._type, self._geo_code, self.values)


octal_re = re.compile(r'\\(\d\d\d)')


def _octal_replace(s):
    # See http://docs.aws.amazon.com/Route53/latest/DeveloperGuide/
    #     DomainNameFormat.html
    return octal_re.sub(lambda m: chr(int(m.group(1), 8)), s)


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

    # This should be bumped when there are underlying changes made to the
    # health check config.
    HEALTH_CHECK_VERSION = '0000'

    def __init__(self, id, access_key_id, secret_access_key, max_changes=1000,
                 *args, **kwargs):
        self.max_changes = max_changes
        self.log = logging.getLogger('Route53Provider[{}]'.format(id))
        self.log.debug('__init__: id=%s, access_key_id=%s, '
                       'secret_access_key=***', id, access_key_id)
        super(Route53Provider, self).__init__(id, *args, **kwargs)
        self._conn = client('route53', aws_access_key_id=access_key_id,
                            aws_secret_access_key=secret_access_key)

        self._r53_zones = None
        self._r53_rrsets = {}
        self._health_checks = None

    def supports(self, record):
        return record._type != 'SSHFP'

    @property
    def r53_zones(self):
        if self._r53_zones is None:
            self.log.debug('r53_zones: loading')
            zones = {}
            more = True
            start = {}
            while more:
                resp = self._conn.list_hosted_zones()
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

    def _data_for_single(self, rrset):
        return {
            'type': rrset['Type'],
            'value': rrset['ResourceRecords'][0]['Value'],
            'ttl': int(rrset['TTL'])
        }

    _data_for_PTR = _data_for_single
    _data_for_CNAME = _data_for_single

    def _data_for_quoted(self, rrset):
        return {
            'type': rrset['Type'],
            'values': [rr['Value'][1:-1] for rr in rrset['ResourceRecords']],
            'ttl': int(rrset['TTL'])
        }

    _data_for_TXT = _data_for_quoted
    _data_for_SPF = _data_for_quoted

    def _data_for_MX(self, rrset):
        values = []
        for rr in rrset['ResourceRecords']:
            priority, value = rr['Value'].split(' ')
            values.append({
                'priority': priority,
                'value': value,
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
                'flags': flags if flags else None,
                'service': service if service else None,
                'regexp': regexp if regexp else None,
                'replacement': replacement if replacement else None,
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

    def populate(self, zone, target=False):
        self.log.debug('populate: name=%s', zone.name)
        before = len(zone.records)

        zone_id = self._get_zone_id(zone.name)
        if zone_id:
            records = defaultdict(lambda: defaultdict(list))
            for rrset in self._load_records(zone_id):
                record_name = zone.hostname_from_fqdn(rrset['Name'])
                record_name = _octal_replace(record_name)
                record_type = rrset['Type']
                if record_type == 'SOA':
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
                    record = Record.new(zone, name, data, source=self)
                    zone.add_record(record)

        self.log.info('populate:   found %s records',
                      len(zone.records) - before)

    def _gen_mods(self, action, records):
        '''
        Turns `_Route53Record`s in to `change_resource_record_sets` `Changes`
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

    def _get_health_check_id(self, record, ident, geo, create):
        # fqdn & the first value are special, we use them to match up health
        # checks to their records. Route53 health checks check a single ip and
        # we're going to assume that ips are interchangeable to avoid
        # health-checking each one independently
        fqdn = record.fqdn
        first_value = geo.values[0]
        self.log.debug('_get_health_check_id: fqdn=%s, type=%s, geo=%s, '
                       'first_value=%s', fqdn, record._type, ident,
                       first_value)

        # health check host can't end with a .
        host = fqdn[:-1]
        # we're looking for a healthcheck with the current version & our record
        # type, we'll ignore anything else
        expected_version_and_type = '{}:{}:'.format(self.HEALTH_CHECK_VERSION,
                                                    record._type)
        for id, health_check in self.health_checks.items():
            if not health_check['CallerReference'] \
               .startswith(expected_version_and_type):
                # not a version & type match, ignore
                continue
            config = health_check['HealthCheckConfig']
            if host == config['FullyQualifiedDomainName'] and \
               first_value == config['IPAddress']:
                # this is the health check we're looking for
                return id

        if not create:
            # no existing matches and not allowed to create, return none
            return

        # no existing matches, we need to create a new health check
        config = {
            'EnableSNI': True,
            'FailureThreshold': 6,
            'FullyQualifiedDomainName': host,
            'IPAddress': first_value,
            'MeasureLatency': True,
            'Port': 443,
            'RequestInterval': 10,
            'ResourcePath': '/_dns',
            'Type': 'HTTPS',
        }
        ref = '{}:{}:{}'.format(self.HEALTH_CHECK_VERSION, record._type,
                                uuid4().hex[:16])
        resp = self._conn.create_health_check(CallerReference=ref,
                                              HealthCheckConfig=config)
        health_check = resp['HealthCheck']
        id = health_check['Id']
        # store the new health check so that we'll be able to find it in the
        # future
        self._health_checks[id] = health_check
        self.log.info('_get_health_check_id: created id=%s, host=%s, '
                      'first_value=%s', id, host, first_value)
        return id

    def _gc_health_checks(self, record, new):
        self.log.debug('_gc_health_checks: record=%s', record)
        # Find the health checks we're using for the new route53 records
        in_use = set()
        for r in new:
            if r.health_check_id:
                in_use.add(r.health_check_id)
        self.log.debug('_gc_health_checks:   in_use=%s', in_use)
        # Now we need to run through ALL the health checks looking for those
        # that apply to this record, deleting any that do and are no longer in
        # use
        host = record.fqdn[:-1]
        for id, health_check in self.health_checks.items():
            config = health_check['HealthCheckConfig']
            _type = health_check['CallerReference'].split(':', 2)[1]
            # if host and the pulled out type match it applies
            if host == config['FullyQualifiedDomainName'] and \
               _type == record._type and id not in in_use:
                # this is a health check for our fqdn & type but not one we're
                # planning to use going forward
                self.log.info('_gc_health_checks:   deleting id=%s', id)
                self._conn.delete_health_check(HealthCheckId=id)

    def _gen_records(self, record, creating=False):
        '''
        Turns an octodns.Record into one or more `_Route53Record`s
        '''
        records = set()
        base = _Route53Record(record.fqdn, record._type, record.ttl,
                              record=record)
        records.add(base)
        if getattr(record, 'geo', False):
            base.is_geo_default = True
            for ident, geo in record.geo.items():
                health_check_id = self._get_health_check_id(record, ident, geo,
                                                            creating)
                records.add(_Route53Record(record.fqdn, record._type,
                                           record.ttl, values=geo.values,
                                           geo=geo,
                                           health_check_id=health_check_id))

        return records

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
        # new one and we have to include some special handling when converting
        # to/from a GEO enabled record
        upserts = set()
        existing_records = {r: r for r in existing_records}
        for new_record in new_records:
            try:
                existing_record = existing_records[new_record]
                if new_record.is_geo_default != existing_record.is_geo_default:
                    # going from normal to geo or geo to normal, need a delete
                    # and create
                    deletes.add(existing_record)
                    creates.add(new_record)
                else:
                    # just an update
                    upserts.add(new_record)
            except KeyError:
                # Completely new record, ignore
                pass

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

    def _extra_changes(self, existing, changes):
        self.log.debug('_extra_changes: existing=%s', existing.name)
        zone_id = self._get_zone_id(existing.name)
        if not zone_id:
            # zone doesn't exist so no extras to worry about
            return []
        # we'll skip extra checking for anything we're already going to change
        changed = set([c.record for c in changes])
        # ok, now it's time for the reason we're here, we need to go over all
        # the existing records
        extra = []
        for record in existing.records:
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
                # we expect a healtcheck now
                try:
                    health_check_id = rrset['HealthCheckId']
                    caller_ref = \
                        self.health_checks[health_check_id]['CallerReference']
                    if caller_ref.startswith(self.HEALTH_CHECK_VERSION):
                        # it has the right health check
                        continue
                except KeyError:
                    # no health check id or one that isn't the right version
                    pass
                # no good, doesn't have the right health check, needs an update
                self.log.debug('_extra_changes:     health-check caused '
                               'update')
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
                # start a new batch with the lefovers
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
