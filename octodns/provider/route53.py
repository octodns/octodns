#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from boto3 import client
from botocore.config import Config
from collections import defaultdict
from incf.countryutils.transformations import cca_to_ctca2
from ipaddress import AddressValueError, ip_address
from uuid import uuid4
import logging
import re

from ..record import Record, Update
from ..record.geo import GeoCodes
from .base import BaseProvider


octal_re = re.compile(r'\\(\d\d\d)')


def _octal_replace(s):
    # See http://docs.aws.amazon.com/Route53/latest/DeveloperGuide/
    #     DomainNameFormat.html
    return octal_re.sub(lambda m: chr(int(m.group(1), 8)), s)


class _Route53Record(object):

    @classmethod
    def _new_dynamic(cls, provider, record, hosted_zone_id, creating):
        # Creates the RRSets that correspond to the given dynamic record
        ret = set()

        # HostedZoneId wants just the last bit, but the place we're getting
        # this from looks like /hostedzone/Z424CArX3BB224
        hosted_zone_id = hosted_zone_id.split('/', 2)[-1]

        # Create the default pool which comes from the base `values` of the
        # record object. Its only used if all other values fail their
        # healthchecks, which hopefully never happens.
        fqdn = record.fqdn
        ret.add(_Route53Record(provider, record, creating,
                               '_octodns-default-pool.{}'.format(fqdn)))

        # Pools
        for pool_name, pool in record.dynamic.pools.items():

            # Create the primary, this will be the rrset that geo targeted
            # rrsets will point to when they want to use a pool of values. It's
            # a primary and observes target health so if all the values for
            # this pool go red, we'll use the fallback/SECONDARY just below
            ret.add(_Route53DynamicPool(provider, hosted_zone_id, record,
                                        pool_name, creating))

            # Create the fallback for this pool
            fallback = pool.data.get('fallback', False)
            if fallback:
                # We have an explicitly configured fallback, another pool to
                # use if all our values go red. This RRSet configures that pool
                # as the next best option
                ret.add(_Route53DynamicPool(provider, hosted_zone_id, record,
                                            pool_name, creating,
                                            target_name=fallback))
            else:
                # We fallback on the default, no explicit fallback so if all of
                # this pool's values go red we'll fallback to the base
                # (non-health-checked) default pool of values
                ret.add(_Route53DynamicPool(provider, hosted_zone_id, record,
                                            pool_name, creating,
                                            target_name='default'))

            # Create the values for this pool. These are health checked and in
            # general each unique value will have an associated healthcheck.
            # The PRIMARY pool up above will point to these RRSets which will
            # be served out according to their weights
            for i, value in enumerate(pool.data['values']):
                weight = value['weight']
                value = value['value']
                ret.add(_Route53DynamicValue(provider, record, pool_name,
                                             value, weight, i, creating))

        # Rules
        for i, rule in enumerate(record.dynamic.rules):
            pool_name = rule.data['pool']
            geos = rule.data.get('geos', [])
            if geos:
                for geo in geos:
                    # Create a RRSet for each geo in each rule that uses the
                    # desired target pool
                    ret.add(_Route53DynamicRule(provider, hosted_zone_id,
                                                record, pool_name, i,
                                                creating, geo=geo))
            else:
                # There's no geo's for this rule so it's the catchall that will
                # just point things that don't match any geo rules to the
                # specified pool
                ret.add(_Route53DynamicRule(provider, hosted_zone_id, record,
                                            pool_name, i, creating))

        return ret

    @classmethod
    def _new_geo(cls, provider, record, creating):
        # Creates the RRSets that correspond to the given geo record
        ret = set()

        ret.add(_Route53GeoDefault(provider, record, creating))
        for ident, geo in record.geo.items():
            ret.add(_Route53GeoRecord(provider, record, ident, geo,
                                      creating))

        return ret

    @classmethod
    def new(cls, provider, record, hosted_zone_id, creating):
        # Creates the RRSets that correspond to the given record

        if getattr(record, 'dynamic', False):
            ret = cls._new_dynamic(provider, record, hosted_zone_id, creating)
            return ret
        elif getattr(record, 'geo', False):
            return cls._new_geo(provider, record, creating)

        # Its a simple record that translates into a single RRSet
        return set((_Route53Record(provider, record, creating),))

    def __init__(self, provider, record, creating, fqdn_override=None):
        self.fqdn = fqdn_override or record.fqdn
        self._type = record._type
        self.ttl = record.ttl

        values_for = getattr(self, '_values_for_{}'.format(self._type))
        self.values = values_for(record)

    def mod(self, action, existing_rrsets):
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

    def _value_convert_value(self, value, record):
        return value

    _value_convert_A = _value_convert_value
    _value_convert_AAAA = _value_convert_value
    _value_convert_NS = _value_convert_value
    _value_convert_CNAME = _value_convert_value
    _value_convert_PTR = _value_convert_value

    def _values_for_values(self, record):
        return record.values

    _values_for_A = _values_for_values
    _values_for_AAAA = _values_for_values
    _values_for_NS = _values_for_values

    def _value_convert_CAA(self, value, record):
        return '{} {} "{}"'.format(value.flags, value.tag, value.value)

    def _values_for_CAA(self, record):
        return [self._value_convert_CAA(v, record) for v in record.values]

    def _values_for_value(self, record):
        return [record.value]

    _values_for_CNAME = _values_for_value
    _values_for_PTR = _values_for_value

    def _value_convert_MX(self, value, record):
        return '{} {}'.format(value.preference, value.exchange)

    def _values_for_MX(self, record):
        return [self._value_convert_MX(v, record) for v in record.values]

    def _value_convert_NAPTR(self, value, record):
        return '{} {} "{}" "{}" "{}" {}' \
            .format(value.order, value.preference,
                    value.flags if value.flags else '',
                    value.service if value.service else '',
                    value.regexp if value.regexp else '',
                    value.replacement)

    def _values_for_NAPTR(self, record):
        return [self._value_convert_NAPTR(v, record) for v in record.values]

    def _value_convert_quoted(self, value, record):
        return record.chunked_value(value)

    _value_convert_SPF = _value_convert_quoted
    _value_convert_TXT = _value_convert_quoted

    def _values_for_quoted(self, record):
        return record.chunked_values

    _values_for_SPF = _values_for_quoted
    _values_for_TXT = _values_for_quoted

    def _value_for_SRV(self, value, record):
        return '{} {} {} {}'.format(value.priority, value.weight,
                                    value.port, value.target)

    def _values_for_SRV(self, record):
        return [self._value_for_SRV(v, record) for v in record.values]


class _Route53DynamicPool(_Route53Record):

    def __init__(self, provider, hosted_zone_id, record, pool_name, creating,
                 target_name=None):
        fqdn_override = '_octodns-{}-pool.{}'.format(pool_name, record.fqdn)
        super(_Route53DynamicPool, self) \
            .__init__(provider, record, creating, fqdn_override=fqdn_override)

        self.hosted_zone_id = hosted_zone_id
        self.pool_name = pool_name

        self.target_name = target_name
        if target_name:
            # We're pointing down the chain
            self.target_dns_name = '_octodns-{}-pool.{}'.format(target_name,
                                                                record.fqdn)
        else:
            # We're a paimary, point at our values
            self.target_dns_name = '_octodns-{}-value.{}'.format(pool_name,
                                                                 record.fqdn)

    @property
    def mode(self):
        return 'Secondary' if self.target_name else 'Primary'

    @property
    def identifer(self):
        if self.target_name:
            return '{}-{}-{}'.format(self.pool_name, self.mode,
                                     self.target_name)
        return '{}-{}'.format(self.pool_name, self.mode)

    def mod(self, action, existing_rrsets):
        return {
            'Action': action,
            'ResourceRecordSet': {
                'AliasTarget': {
                    'DNSName': self.target_dns_name,
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': self.hosted_zone_id,
                },
                'Failover': 'SECONDARY' if self.target_name else 'PRIMARY',
                'Name': self.fqdn,
                'SetIdentifier': self.identifer,
                'Type': self._type,
            }
        }

    def __hash__(self):
        return '{}:{}:{}'.format(self.fqdn, self._type,
                                 self.identifer).__hash__()

    def __repr__(self):
        return '_Route53DynamicPool<{} {} {} {}>' \
            .format(self.fqdn, self._type, self.mode, self.target_dns_name)


class _Route53DynamicRule(_Route53Record):

    def __init__(self, provider, hosted_zone_id, record, pool_name, index,
                 creating, geo=None):
        super(_Route53DynamicRule, self).__init__(provider, record, creating)

        self.hosted_zone_id = hosted_zone_id
        self.geo = geo
        self.pool_name = pool_name
        self.index = index

        self.target_dns_name = '_octodns-{}-pool.{}'.format(pool_name,
                                                            record.fqdn)

    @property
    def identifer(self):
        return '{}-{}-{}'.format(self.index, self.pool_name, self.geo)

    def mod(self, action, existing_rrsets):
        rrset = {
            'AliasTarget': {
                'DNSName': self.target_dns_name,
                'EvaluateTargetHealth': True,
                'HostedZoneId': self.hosted_zone_id,
            },
            'GeoLocation': {
                'CountryCode': '*'
            },
            'Name': self.fqdn,
            'SetIdentifier': self.identifer,
            'Type': self._type,
        }

        if self.geo:
            geo = GeoCodes.parse(self.geo)

            if geo['province_code']:
                rrset['GeoLocation'] = {
                    'CountryCode': geo['country_code'],
                    'SubdivisionCode': geo['province_code'],
                }
            elif geo['country_code']:
                rrset['GeoLocation'] = {
                    'CountryCode': geo['country_code']
                }
            else:
                rrset['GeoLocation'] = {
                    'ContinentCode': geo['continent_code'],
                }

        return {
            'Action': action,
            'ResourceRecordSet': rrset,
        }

    def __hash__(self):
        return '{}:{}:{}'.format(self.fqdn, self._type,
                                 self.identifer).__hash__()

    def __repr__(self):
        return '_Route53DynamicRule<{} {} {} {} {}>' \
            .format(self.fqdn, self._type, self.index, self.geo,
                    self.target_dns_name)


class _Route53DynamicValue(_Route53Record):

    def __init__(self, provider, record, pool_name, value, weight, index,
                 creating):
        fqdn_override = '_octodns-{}-value.{}'.format(pool_name, record.fqdn)
        super(_Route53DynamicValue, self).__init__(provider, record, creating,
                                                   fqdn_override=fqdn_override)

        self.pool_name = pool_name
        self.index = index
        value_convert = getattr(self, '_value_convert_{}'.format(record._type))
        self.value = value_convert(value, record)
        self.weight = weight

        self.health_check_id = provider.get_health_check_id(record, self.value,
                                                            creating)

    @property
    def identifer(self):
        return '{}-{:03d}'.format(self.pool_name, self.index)

    def mod(self, action, existing_rrsets):

        if action == 'DELETE':
            # When deleting records try and find the original rrset so that
            # we're 100% sure to have the complete & accurate data (this mostly
            # ensures we have the right health check id when there's multiple
            # potential matches)
            for existing in existing_rrsets:
                if self.fqdn == existing.get('Name') and \
                   self.identifer == existing.get('SetIdentifier', None):
                    return {
                        'Action': action,
                        'ResourceRecordSet': existing,
                    }

        return {
            'Action': action,
            'ResourceRecordSet': {
                'HealthCheckId': self.health_check_id,
                'Name': self.fqdn,
                'ResourceRecords': [{'Value': self.value}],
                'SetIdentifier': self.identifer,
                'TTL': self.ttl,
                'Type': self._type,
                'Weight': self.weight,
            }
        }

    def __hash__(self):
        return '{}:{}:{}'.format(self.fqdn, self._type,
                                 self.identifer).__hash__()

    def __repr__(self):
        return '_Route53DynamicValue<{} {} {} {}>' \
            .format(self.fqdn, self._type, self.identifer, self.value)


class _Route53GeoDefault(_Route53Record):

    def mod(self, action, existing_rrsets):
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

        value = geo.values[0]
        self.health_check_id = provider.get_health_check_id(record, value,
                                                            creating)

    def mod(self, action, existing_rrsets):
        geo = self.geo
        set_identifier = geo.code
        fqdn = self.fqdn

        if action == 'DELETE':
            # When deleting records try and find the original rrset so that
            # we're 100% sure to have the complete & accurate data (this mostly
            # ensures we have the right health check id when there's multiple
            # potential matches)
            for existing in existing_rrsets:
                if fqdn == existing.get('Name') and \
                   set_identifier == existing.get('SetIdentifier', None):
                    return {
                        'Action': action,
                        'ResourceRecordSet': existing,
                    }

        rrset = {
            'Name': self.fqdn,
            'GeoLocation': {
                'CountryCode': '*'
            },
            'ResourceRecords': [{'Value': v} for v in geo.values],
            'SetIdentifier': set_identifier,
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


def _mod_keyer(mod):
    rrset = mod['ResourceRecordSet']

    # Route53 requires that changes are ordered such that a target of an
    # AliasTarget is created or upserted prior to the record that targets it.
    # This is complicated by "UPSERT" appearing to be implemented as "DELETE"
    # before all changes, followed by a "CREATE", internally in the AWS API.
    # Because of this, we order changes as follows:
    #   - Delete any records that we wish to delete that are GEOS
    #      (because they are never targetted by anything)
    #   - Delete any records that we wish to delete that are SECONDARY
    #      (because they are no longer targetted by GEOS)
    #   - Delete any records that we wish to delete that are PRIMARY
    #      (because they are no longer targetted by SECONDARY)
    #   - Delete any records that we wish to delete that are VALUES
    #      (because they are no longer targetted by PRIMARY)
    #   - CREATE/UPSERT any records that are VALUES
    #      (because they don't depend on other records)
    #   - CREATE/UPSERT any records that are PRIMARY
    #      (because they always point to VALUES which now exist)
    #   - CREATE/UPSERT any records that are SECONDARY
    #      (because they now have PRIMARY records to target)
    #   - CREATE/UPSERT any records that are GEOS
    #      (because they now have all their PRIMARY pools to target)
    #   - :tada:
    #
    # In theory we could also do this based on actual target reference
    # checking, but that's more complex. Since our rules have a known
    # dependency order, we just rely on that.

    # Get the unique ID from the name/id to get a consistent ordering.
    if rrset.get('GeoLocation', False):
        unique_id = rrset['SetIdentifier']
    else:
        unique_id = rrset['Name']

    # Prioritise within the action_priority, ensuring targets come first.
    if rrset.get('GeoLocation', False):
        # Geos reference pools, so they come last.
        record_priority = 3
    elif rrset.get('AliasTarget', False):
        # We use an alias
        if rrset.get('Failover', False) == 'SECONDARY':
            # We're a secondary, which reference the primary (failover, P1).
            record_priority = 2
        else:
            # We're a primary, we reference values (P0).
            record_priority = 1
    else:
        # We're just a plain value, has no dependencies so first.
        record_priority = 0

    if mod['Action'] == 'DELETE':
        # Delete things first, so we can never trounce our own additions
        action_priority = 0
        # Delete in the reverse order of priority, e.g. start with the deepest
        # reference and work back to the values, rather than starting at the
        # values (still ref'd).
        record_priority = -record_priority
    else:
        # For CREATE and UPSERT, Route53 seems to treat them the same, so
        # interleave these, keeping the reference order described above.
        action_priority = 1

    return (action_priority, record_priority, unique_id)


def _parse_pool_name(n):
    # Parse the pool name out of _octodns-<pool-name>-pool...
    return n.split('.', 1)[0][9:-5]


class Route53Provider(BaseProvider):
    '''
    AWS Route53 Provider

    route53:
        class: octodns.provider.route53.Route53Provider
        # The AWS access key id
        access_key_id:
        # The AWS secret access key
        secret_access_key:
        # The AWS session token (optional)
        # Only needed if using temporary security credentials
        session_token:

    Alternatively, you may leave out access_key_id, secret_access_key
    and session_token.
    This will result in boto3 deciding authentication dynamically.

    In general the account used will need full permissions on Route53.
    '''
    SUPPORTS_GEO = True
    SUPPORTS_DYNAMIC = True
    SUPPORTS = set(('A', 'AAAA', 'CAA', 'CNAME', 'MX', 'NAPTR', 'NS', 'PTR',
                    'SPF', 'SRV', 'TXT'))

    # This should be bumped when there are underlying changes made to the
    # health check config.
    HEALTH_CHECK_VERSION = '0001'

    def __init__(self, id, access_key_id=None, secret_access_key=None,
                 max_changes=1000, client_max_attempts=None,
                 session_token=None, *args, **kwargs):
        self.max_changes = max_changes
        _msg = 'access_key_id={}, secret_access_key=***, ' \
               'session_token=***'.format(access_key_id)
        use_fallback_auth = access_key_id is None and \
            secret_access_key is None and session_token is None
        if use_fallback_auth:
            _msg = 'auth=fallback'
        self.log = logging.getLogger('Route53Provider[{}]'.format(id))
        self.log.debug('__init__: id=%s, %s', id, _msg)
        super(Route53Provider, self).__init__(id, *args, **kwargs)

        config = None
        if client_max_attempts is not None:
            self.log.info('__init__: setting max_attempts to %d',
                          client_max_attempts)
            config = Config(retries={'max_attempts': client_max_attempts})

        if use_fallback_auth:
            self._conn = client('route53', config=config)
        else:
            self._conn = client('route53', aws_access_key_id=access_key_id,
                                aws_secret_access_key=secret_access_key,
                                aws_session_token=session_token,
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

    def _data_for_dynamic(self, name, _type, rrsets):
        # This converts a bunch of RRSets into their corresponding dynamic
        # Record. It's used by populate.
        pools = defaultdict(lambda: {'values': []})
        # Data to build our rules will be collected here and "converted" into
        # their final form below
        rules = defaultdict(lambda: {'pool': None, 'geos': []})
        # Base/empty data
        data = {
            'dynamic': {
                'pools': pools,
                'rules': [],
            }
        }

        # For all the rrsets that comprise this dynamic record
        for rrset in rrsets:
            name = rrset['Name']
            if '-pool.' in name:
                # This is a pool rrset
                pool_name = _parse_pool_name(name)
                if pool_name == 'default':
                    # default becomes the base for the record and its
                    # value(s) will fill the non-dynamic values
                    data_for = getattr(self, '_data_for_{}'.format(_type))
                    data.update(data_for(rrset))
                elif rrset['Failover'] == 'SECONDARY':
                    # This is a failover record, we'll ignore PRIMARY, but
                    # SECONDARY will tell us what the pool's fallback is
                    fallback_name = \
                        _parse_pool_name(rrset['AliasTarget']['DNSName'])
                    # Don't care about default fallbacks, anything else
                    # we'll record
                    if fallback_name != 'default':
                        pools[pool_name]['fallback'] = fallback_name
            elif 'GeoLocation' in rrset:
                # These are rules
                _id = rrset['SetIdentifier']
                # We record rule index as the first part of set-id, the 2nd
                # part just ensures uniqueness across geos and is ignored
                i = int(_id.split('-', 1)[0])
                target_pool = _parse_pool_name(rrset['AliasTarget']['DNSName'])
                # Record the pool
                rules[i]['pool'] = target_pool
                # Record geo if we have one
                geo = self._parse_geo(rrset)
                if geo:
                    rules[i]['geos'].append(geo)
            else:
                # These are the pool value(s)
                # Grab the pool name out of the SetIdentifier, format looks
                # like ...-000 where 000 is a zero-padded index for the value
                # it's ignored only used to make sure the value is unique
                pool_name = rrset['SetIdentifier'][:-4]
                value = rrset['ResourceRecords'][0]['Value']
                pools[pool_name]['values'].append({
                    'value': value,
                    'weight': rrset['Weight'],
                })

        # Convert our map of rules into an ordered list now that we have all
        # the data
        for _, rule in sorted(rules.items()):
            r = {
                'pool': rule['pool'],
            }
            geos = sorted(rule['geos'])
            if geos:
                r['geos'] = geos
            data['dynamic']['rules'].append(r)

        return data

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        before = len(zone.records)
        exists = False

        zone_id = self._get_zone_id(zone.name)
        if zone_id:
            exists = True
            records = defaultdict(lambda: defaultdict(list))
            dynamic = defaultdict(lambda: defaultdict(list))

            for rrset in self._load_records(zone_id):
                record_name = zone.hostname_from_fqdn(rrset['Name'])
                record_name = _octal_replace(record_name)
                record_type = rrset['Type']
                if record_type not in self.SUPPORTS:
                    # Skip stuff we don't support
                    continue
                if record_name.startswith('_octodns-'):
                    # Part of a dynamic record
                    try:
                        record_name = record_name.split('.', 1)[1]
                    except IndexError:
                        record_name = ''
                    dynamic[record_name][record_type].append(rrset)
                    continue
                elif 'AliasTarget' in rrset:
                    if rrset['AliasTarget']['DNSName'].startswith('_octodns-'):
                        # Part of a dynamic record
                        dynamic[record_name][record_type].append(rrset)
                    else:
                        # Alias records are Route53 specific and are not
                        # portable, so we need to skip them
                        self.log.warning("%s is an Alias record. Skipping..."
                                         % rrset['Name'])
                    continue
                # A basic record (potentially including geo)
                data = getattr(self, '_data_for_{}'.format(record_type))(rrset)
                records[record_name][record_type].append(data)

            # Convert the dynamic rrsets to Records
            for name, types in dynamic.items():
                for _type, rrsets in types.items():
                    data = self._data_for_dynamic(name, _type, rrsets)
                    record = Record.new(zone, name, data, source=self,
                                        lenient=lenient)
                    zone.add_record(record, lenient=lenient)

            # Convert the basic (potentially with geo) rrsets to records
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
                    zone.add_record(record, lenient=lenient)

        self.log.info('populate:   found %s records, exists=%s',
                      len(zone.records) - before, exists)
        return exists

    def _gen_mods(self, action, records, existing_rrsets):
        '''
        Turns `_Route53*`s in to `change_resource_record_sets` `Changes`
        '''
        return [r.mod(action, existing_rrsets) for r in records]

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

    def _healthcheck_measure_latency(self, record):
        return record._octodns.get('route53', {}) \
            .get('healthcheck', {}) \
            .get('measure_latency', True)

    def _health_check_equivilent(self, host, path, protocol, port,
                                 measure_latency, health_check, value=None):
        config = health_check['HealthCheckConfig']

        # So interestingly Route53 normalizes IPAddress which will cause us to
        # fail to find see things as equivalent. To work around this we'll
        # ip_address's returned object for equivalence
        # E.g 2001:4860:4860::8842 -> 2001:4860:4860:0:0:0:0:8842
        if value:
            value = ip_address(unicode(value))
            config_ip_address = ip_address(unicode(config['IPAddress']))
        else:
            # No value so give this a None to match value's
            config_ip_address = None

        return host == config['FullyQualifiedDomainName'] and \
            path == config['ResourcePath'] and protocol == config['Type'] \
            and port == config['Port'] and \
            measure_latency == config['MeasureLatency'] and \
            value == config_ip_address

    def get_health_check_id(self, record, value, create):
        # fqdn & the first value are special, we use them to match up health
        # checks to their records. Route53 health checks check a single ip and
        # we're going to assume that ips are interchangeable to avoid
        # health-checking each one independently
        fqdn = record.fqdn
        self.log.debug('get_health_check_id: fqdn=%s, type=%s, value=%s',
                       fqdn, record._type, value)

        try:
            ip_address(unicode(value))
            # We're working with an IP, host is the Host header
            healthcheck_host = record.healthcheck_host
        except (AddressValueError, ValueError):
            # This isn't an IP, host is the value, value should be None
            healthcheck_host = value
            value = None

        healthcheck_path = record.healthcheck_path
        healthcheck_protocol = record.healthcheck_protocol
        healthcheck_port = record.healthcheck_port
        healthcheck_latency = self._healthcheck_measure_latency(record)

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
                                             healthcheck_port,
                                             healthcheck_latency,
                                             health_check,
                                             value=value):
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
            'MeasureLatency': healthcheck_latency,
            'Port': healthcheck_port,
            'RequestInterval': 10,
            'ResourcePath': healthcheck_path,
            'Type': healthcheck_protocol,
        }
        if value:
            config['IPAddress'] = value

        ref = '{}:{}:{}:{}'.format(self.HEALTH_CHECK_VERSION, record._type,
                                   record.fqdn, uuid4().hex[:12])
        resp = self._conn.create_health_check(CallerReference=ref,
                                              HealthCheckConfig=config)
        health_check = resp['HealthCheck']
        id = health_check['Id']

        # Set a Name for the benefit of the UI
        name = '{}:{} - {}'.format(record.fqdn, record._type,
                                   value or healthcheck_host)
        self._conn.change_tags_for_resource(ResourceType='healthcheck',
                                            ResourceId=id,
                                            AddTags=[{
                                                'Key': 'Name',
                                                'Value': name,
                                            }])
        # Manually add it to our cache
        health_check['Tags'] = {
            'Name': name
        }

        # store the new health check so that we'll be able to find it in the
        # future
        self._health_checks[id] = health_check
        self.log.info('get_health_check_id: created id=%s, host=%s, '
                      'path=%s, protocol=%s, port=%d, measure_latency=%r, '
                      'value=%s', id, healthcheck_host, healthcheck_path,
                      healthcheck_protocol, healthcheck_port,
                      healthcheck_latency, value)
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

    def _gen_records(self, record, zone_id, creating=False):
        '''
        Turns an octodns.Record into one or more `_Route53*`s
        '''
        return _Route53Record.new(self, record, zone_id, creating)

    def _mod_Create(self, change, zone_id, existing_rrsets):
        # New is the stuff that needs to be created
        new_records = self._gen_records(change.new, zone_id, creating=True)
        # Now is a good time to clear out any unused health checks since we
        # know what we'll be using going forward
        self._gc_health_checks(change.new, new_records)
        return self._gen_mods('CREATE', new_records, existing_rrsets)

    def _mod_Update(self, change, zone_id, existing_rrsets):
        # See comments in _Route53Record for how the set math is made to do our
        # bidding here.
        existing_records = self._gen_records(change.existing, zone_id,
                                             creating=False)
        new_records = self._gen_records(change.new, zone_id, creating=True)
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

        return self._gen_mods('DELETE', deletes, existing_rrsets) + \
            self._gen_mods('CREATE', creates, existing_rrsets) + \
            self._gen_mods('UPSERT', upserts, existing_rrsets)

    def _mod_Delete(self, change, zone_id, existing_rrsets):
        # Existing is the thing that needs to be deleted
        existing_records = self._gen_records(change.existing, zone_id,
                                             creating=False)
        # Now is a good time to clear out all the health checks since we know
        # we're done with them
        self._gc_health_checks(change.existing, [])
        return self._gen_mods('DELETE', existing_records, existing_rrsets)

    def _extra_changes_update_needed(self, record, rrset):
        healthcheck_host = record.healthcheck_host
        healthcheck_path = record.healthcheck_path
        healthcheck_protocol = record.healthcheck_protocol
        healthcheck_port = record.healthcheck_port
        healthcheck_latency = self._healthcheck_measure_latency(record)

        try:
            health_check_id = rrset['HealthCheckId']
            health_check = self.health_checks[health_check_id]
            caller_ref = health_check['CallerReference']
            if caller_ref.startswith(self.HEALTH_CHECK_VERSION):
                if self._health_check_equivilent(healthcheck_host,
                                                 healthcheck_path,
                                                 healthcheck_protocol,
                                                 healthcheck_port,
                                                 healthcheck_latency,
                                                 health_check):
                    # it has the right health check
                    return False
        except (IndexError, KeyError):
            # no health check id or one that isn't the right version
            pass

        # no good, doesn't have the right health check, needs an update
        self.log.info('_extra_changes_update_needed: health-check caused '
                      'update of %s:%s', record.fqdn, record._type)
        return True

    def _extra_changes_geo_needs_update(self, zone_id, record):
        # OK this is a record we don't have change for that does have geo
        # information. We need to look and see if it needs to be updated b/c of
        # a health check version bump or other mismatch
        self.log.debug('_extra_changes_geo_needs_update: inspecting=%s, %s',
                       record.fqdn, record._type)

        fqdn = record.fqdn

        # loop through all the r53 rrsets
        for rrset in self._load_records(zone_id):
            if fqdn == rrset['Name'] and record._type == rrset['Type'] and \
               rrset.get('GeoLocation', {}).get('CountryCode', False) != '*' \
               and self._extra_changes_update_needed(record, rrset):
                # no good, doesn't have the right health check, needs an update
                self.log.info('_extra_changes_geo_needs_update: health-check '
                              'caused update of %s:%s', record.fqdn,
                              record._type)
                return True

        return False

    def _extra_changes_dynamic_needs_update(self, zone_id, record):
        # OK this is a record we don't have change for that does have dynamic
        # information. We need to look and see if it needs to be updated b/c of
        # a health check version bump or other mismatch
        self.log.debug('_extra_changes_dynamic_needs_update: inspecting=%s, '
                       '%s', record.fqdn, record._type)

        fqdn = record.fqdn
        _type = record._type

        # loop through all the r53 rrsets
        for rrset in self._load_records(zone_id):
            name = rrset['Name']
            # Break off the first piece of the name, it'll let us figure out if
            # this is an rrset we're interested in.
            maybe_meta, rest = name.split('.', 1)

            if not maybe_meta.startswith('_octodns-') or \
               not maybe_meta.endswith('-value') or \
               '-default-' in name:
                # We're only interested in non-default dynamic value records,
                # as that's where healthchecks live
                continue

            if rest != fqdn or _type != rrset['Type']:
                # rrset isn't for the current record
                continue

            if self._extra_changes_update_needed(record, rrset):
                # no good, doesn't have the right health check, needs an update
                self.log.info('_extra_changes_dynamic_needs_update: '
                              'health-check caused update of %s:%s',
                              record.fqdn, record._type)
                return True

        return False

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
        extras = []
        for record in desired.records:
            if record in changed:
                # already have a change for it, skipping
                continue

            if getattr(record, 'geo', False):
                if self._extra_changes_geo_needs_update(zone_id, record):
                    extras.append(Update(record, record))
            elif getattr(record, 'dynamic', False):
                if self._extra_changes_dynamic_needs_update(zone_id, record):
                    extras.append(Update(record, record))

        return extras

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.info('_apply: zone=%s, len(changes)=%d', desired.name,
                      len(changes))

        batch = []
        batch_rs_count = 0
        zone_id = self._get_zone_id(desired.name, True)
        existing_rrsets = self._load_records(zone_id)
        for c in changes:
            # Generate the mods for this change
            mod_type = getattr(self, '_mod_{}'.format(c.__class__.__name__))
            mods = mod_type(c, zone_id, existing_rrsets)

            # Order our mods to make sure targets exist before alises point to
            # them and we CRUD in the desired order
            mods.sort(key=_mod_keyer)

            mods_rs_count = sum(
                [len(m['ResourceRecordSet'].get('ResourceRecords', ''))
                 for m in mods]
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
