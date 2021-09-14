#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from ipaddress import IPv4Address, IPv6Address
from logging import getLogger
import re

from six import string_types, text_type
from fqdn import FQDN

from ..equality import EqualityTupleMixin
from .geo import GeoCodes


class Change(object):

    def __init__(self, existing, new):
        self.existing = existing
        self.new = new

    @property
    def record(self):
        'Returns new if we have one, existing otherwise'
        return self.new or self.existing

    def __lt__(self, other):
        self_record = self.record
        other_record = other.record
        return ((self_record.name, self_record._type) <
                (other_record.name, other_record._type))


class Create(Change):

    def __init__(self, new):
        super(Create, self).__init__(None, new)

    def __repr__(self, leader=''):
        source = self.new.source.id if self.new.source else ''
        return 'Create {} ({})'.format(self.new, source)


class Update(Change):

    # Leader is just to allow us to work around heven eating leading whitespace
    # in our output. When we call this from the Manager.sync plan summary
    # section we'll pass in a leader, otherwise we'll just let it default and
    # do nothing
    def __repr__(self, leader=''):
        source = self.new.source.id if self.new.source else ''
        return 'Update\n{leader}    {existing} ->\n{leader}    {new} ({src})' \
            .format(existing=self.existing, new=self.new, leader=leader,
                    src=source)


class Delete(Change):

    def __init__(self, existing):
        super(Delete, self).__init__(existing, None)

    def __repr__(self, leader=''):
        return 'Delete {}'.format(self.existing)


class ValidationError(Exception):

    @classmethod
    def build_message(cls, fqdn, reasons):
        return 'Invalid record {}\n  - {}'.format(fqdn, '\n  - '.join(reasons))

    def __init__(self, fqdn, reasons):
        super(Exception, self).__init__(self.build_message(fqdn, reasons))
        self.fqdn = fqdn
        self.reasons = reasons


class Record(EqualityTupleMixin):
    log = getLogger('Record')

    @classmethod
    def new(cls, zone, name, data, source=None, lenient=False):
        name = text_type(name)
        fqdn = '{}.{}'.format(name, zone.name) if name else zone.name
        try:
            _type = data['type']
        except KeyError:
            raise Exception('Invalid record {}, missing type'.format(fqdn))
        try:
            _class = {
                'A': ARecord,
                'AAAA': AaaaRecord,
                'ALIAS': AliasRecord,
                'CAA': CaaRecord,
                'CNAME': CnameRecord,
                'DNAME': DnameRecord,
                'LOC': LocRecord,
                'MX': MxRecord,
                'NAPTR': NaptrRecord,
                'NS': NsRecord,
                'PTR': PtrRecord,
                'SPF': SpfRecord,
                'SRV': SrvRecord,
                'SSHFP': SshfpRecord,
                'TXT': TxtRecord,
                'URLFWD': UrlfwdRecord,
            }[_type]
        except KeyError:
            raise Exception('Unknown record type: "{}"'.format(_type))
        reasons = _class.validate(name, fqdn, data)
        try:
            lenient |= data['octodns']['lenient']
        except KeyError:
            pass
        if reasons:
            if lenient:
                cls.log.warn(ValidationError.build_message(fqdn, reasons))
            else:
                raise ValidationError(fqdn, reasons)
        return _class(zone, name, data, source=source)

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = []
        n = len(fqdn)
        if n > 253:
            reasons.append('invalid fqdn, "{}" is too long at {} chars, max '
                           'is 253'.format(fqdn, n))
        for label in name.split('.'):
            n = len(label)
            if n > 63:
                reasons.append('invalid label, "{}" is too long at {} chars, '
                               'max is 63'.format(label, n))
        try:
            ttl = int(data['ttl'])
            if ttl < 0:
                reasons.append('invalid ttl')
        except KeyError:
            reasons.append('missing ttl')
        try:
            if data['octodns']['healthcheck']['protocol'] \
               not in ('HTTP', 'HTTPS', 'TCP'):
                reasons.append('invalid healthcheck protocol')
        except KeyError:
            pass
        return reasons

    def __init__(self, zone, name, data, source=None):
        self.log.debug('__init__: zone.name=%s, type=%11s, name=%s', zone.name,
                       self.__class__.__name__, name)
        self.zone = zone
        # force everything lower-case just to be safe
        self.name = text_type(name).lower() if name else name
        self.source = source
        self.ttl = int(data['ttl'])

        self._octodns = data.get('octodns', {})

    def _data(self):
        return {'ttl': self.ttl}

    @property
    def data(self):
        return self._data()

    @property
    def fqdn(self):
        if self.name:
            return '{}.{}'.format(self.name, self.zone.name)
        return self.zone.name

    @property
    def ignored(self):
        return self._octodns.get('ignored', False)

    @property
    def excluded(self):
        return self._octodns.get('excluded', [])

    @property
    def included(self):
        return self._octodns.get('included', [])

    def healthcheck_host(self, value=None):
        healthcheck = self._octodns.get('healthcheck', {})
        if healthcheck.get('protocol', None) == 'TCP':
            return None
        return healthcheck.get('host', self.fqdn[:-1]) or value

    @property
    def healthcheck_path(self):
        healthcheck = self._octodns.get('healthcheck', {})
        if healthcheck.get('protocol', None) == 'TCP':
            return None
        try:
            return healthcheck['path']
        except KeyError:
            return '/_dns'

    @property
    def healthcheck_protocol(self):
        try:
            return self._octodns['healthcheck']['protocol']
        except KeyError:
            return 'HTTPS'

    @property
    def healthcheck_port(self):
        try:
            return int(self._octodns['healthcheck']['port'])
        except KeyError:
            return 443

    def changes(self, other, target):
        # We're assuming we have the same name and type if we're being compared
        if self.ttl != other.ttl:
            return Update(self, other)

    def copy(self, zone=None):
        data = self.data
        data['type'] = self._type

        return Record.new(
            zone if zone else self.zone,
            self.name,
            data,
            self.source,
            lenient=True
        )

    # NOTE: we're using __hash__ and ordering methods that consider Records
    # equivalent if they have the same name & _type. Values are ignored. This
    # is useful when computing diffs/changes.

    def __hash__(self):
        return '{}:{}'.format(self.name, self._type).__hash__()

    def _equality_tuple(self):
        return (self.name, self._type)

    def __repr__(self):
        # Make sure this is always overridden
        raise NotImplementedError('Abstract base class, __repr__ required')


class GeoValue(EqualityTupleMixin):
    geo_re = re.compile(r'^(?P<continent_code>\w\w)(-(?P<country_code>\w\w)'
                        r'(-(?P<subdivision_code>\w\w))?)?$')

    @classmethod
    def _validate_geo(cls, code):
        reasons = []
        match = cls.geo_re.match(code)
        if not match:
            reasons.append('invalid geo "{}"'.format(code))
        return reasons

    def __init__(self, geo, values):
        self.code = geo
        match = self.geo_re.match(geo)
        self.continent_code = match.group('continent_code')
        self.country_code = match.group('country_code')
        self.subdivision_code = match.group('subdivision_code')
        self.values = sorted(values)

    @property
    def parents(self):
        bits = self.code.split('-')[:-1]
        while bits:
            yield '-'.join(bits)
            bits.pop()

    def _equality_tuple(self):
        return (self.continent_code, self.country_code, self.subdivision_code,
                self.values)

    def __repr__(self):
        return "'Geo {} {} {} {}'".format(self.continent_code,
                                          self.country_code,
                                          self.subdivision_code, self.values)


class _ValuesMixin(object):

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = super(_ValuesMixin, cls).validate(name, fqdn, data)

        values = data.get('values', data.get('value', []))

        reasons.extend(cls._value_type.validate(values, cls._type))

        return reasons

    def __init__(self, zone, name, data, source=None):
        super(_ValuesMixin, self).__init__(zone, name, data, source=source)
        try:
            values = data['values']
        except KeyError:
            values = [data['value']]
        self.values = sorted(self._value_type.process(values))

    def changes(self, other, target):
        if self.values != other.values:
            return Update(self, other)
        return super(_ValuesMixin, self).changes(other, target)

    def _data(self):
        ret = super(_ValuesMixin, self)._data()
        if len(self.values) > 1:
            values = [getattr(v, 'data', v) for v in self.values if v]
            if len(values) > 1:
                ret['values'] = values
            elif len(values) == 1:
                ret['value'] = values[0]
        elif len(self.values) == 1:
            v = self.values[0]
            if v:
                ret['value'] = getattr(v, 'data', v)

        return ret

    def __repr__(self):
        values = "['{}']".format("', '".join([text_type(v)
                                              for v in self.values]))
        return '<{} {} {}, {}, {}>'.format(self.__class__.__name__,
                                           self._type, self.ttl,
                                           self.fqdn, values)


class _GeoMixin(_ValuesMixin):
    '''
    Adds GeoDNS support to a record.

    Must be included before `Record`.
    '''

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = super(_GeoMixin, cls).validate(name, fqdn, data)
        try:
            geo = dict(data['geo'])
            for code, values in geo.items():
                reasons.extend(GeoValue._validate_geo(code))
                reasons.extend(cls._value_type.validate(values, cls._type))
        except KeyError:
            pass
        return reasons

    def __init__(self, zone, name, data, *args, **kwargs):
        super(_GeoMixin, self).__init__(zone, name, data, *args, **kwargs)
        try:
            self.geo = dict(data['geo'])
        except KeyError:
            self.geo = {}
        for code, values in self.geo.items():
            self.geo[code] = GeoValue(code, values)

    def _data(self):
        ret = super(_GeoMixin, self)._data()
        if self.geo:
            geo = {}
            for code, value in self.geo.items():
                geo[code] = value.values
            ret['geo'] = geo
        return ret

    def changes(self, other, target):
        if target.SUPPORTS_GEO:
            if self.geo != other.geo:
                return Update(self, other)
        return super(_GeoMixin, self).changes(other, target)

    def __repr__(self):
        if self.geo:
            return '<{} {} {}, {}, {}, {}>'.format(self.__class__.__name__,
                                                   self._type, self.ttl,
                                                   self.fqdn, self.values,
                                                   self.geo)
        return super(_GeoMixin, self).__repr__()


class _ValueMixin(object):

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = super(_ValueMixin, cls).validate(name, fqdn, data)
        reasons.extend(cls._value_type.validate(data.get('value', None),
                                                cls._type))
        return reasons

    def __init__(self, zone, name, data, source=None):
        super(_ValueMixin, self).__init__(zone, name, data, source=source)
        self.value = self._value_type.process(data['value'])

    def changes(self, other, target):
        if self.value != other.value:
            return Update(self, other)
        return super(_ValueMixin, self).changes(other, target)

    def _data(self):
        ret = super(_ValueMixin, self)._data()
        if self.value:
            ret['value'] = getattr(self.value, 'data', self.value)
        return ret

    def __repr__(self):
        return '<{} {} {}, {}, {}>'.format(self.__class__.__name__,
                                           self._type, self.ttl,
                                           self.fqdn, self.value)


class _DynamicPool(object):
    log = getLogger('_DynamicPool')

    def __init__(self, _id, data):
        self._id = _id

        values = [
            {
                'value': d['value'],
                'weight': d.get('weight', 1),
            } for d in data['values']
        ]
        values.sort(key=lambda d: d['value'])

        # normalize weight of a single-value pool
        if len(values) == 1:
            weight = data['values'][0].get('weight', 1)
            if weight != 1:
                self.log.warn(
                    'Using weight=1 instead of %s for single-value pool %s',
                    weight, _id)
                values[0]['weight'] = 1

        fallback = data.get('fallback', None)
        self.data = {
            'fallback': fallback if fallback != 'default' else None,
            'values': values,
        }

    def _data(self):
        return self.data

    def __eq__(self, other):
        if not isinstance(other, _DynamicPool):
            return False
        return self.data == other.data

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return '{}'.format(self.data)


class _DynamicRule(object):

    def __init__(self, i, data):
        self.i = i

        self.data = {}
        try:
            self.data['pool'] = data['pool']
        except KeyError:
            pass
        try:
            self.data['geos'] = sorted(data['geos'])
        except KeyError:
            pass

    def _data(self):
        return self.data

    def __eq__(self, other):
        if not isinstance(other, _DynamicRule):
            return False
        return self.data == other.data

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return '{}'.format(self.data)


class _Dynamic(object):

    def __init__(self, pools, rules):
        self.pools = pools
        self.rules = rules

    def _data(self):
        pools = {}
        for _id, pool in self.pools.items():
            pools[_id] = pool._data()
        rules = []
        for rule in self.rules:
            rules.append(rule._data())
        return {
            'pools': pools,
            'rules': rules,
        }

    def __eq__(self, other):
        if not isinstance(other, _Dynamic):
            return False
        ret = self.pools == other.pools and self.rules == other.rules
        return ret

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return '{}, {}'.format(self.pools, self.rules)


class _DynamicMixin(object):
    geo_re = re.compile(r'^(?P<continent_code>\w\w)(-(?P<country_code>\w\w)'
                        r'(-(?P<subdivision_code>\w\w))?)?$')

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = super(_DynamicMixin, cls).validate(name, fqdn, data)

        if 'dynamic' not in data:
            return reasons
        elif 'geo' in data:
            reasons.append('"dynamic" record with "geo" content')

        try:
            pools = data['dynamic']['pools']
        except KeyError:
            pools = {}

        pools_exist = set()
        pools_seen = set()
        pools_seen_as_fallback = set()
        if not isinstance(pools, dict):
            reasons.append('pools must be a dict')
        elif not pools:
            reasons.append('missing pools')
        else:
            for _id, pool in sorted(pools.items()):
                if not isinstance(pool, dict):
                    reasons.append('pool "{}" must be a dict'.format(_id))
                    continue
                try:
                    values = pool['values']
                except KeyError:
                    reasons.append('pool "{}" is missing values'.format(_id))
                    continue

                pools_exist.add(_id)

                for i, value in enumerate(values):
                    value_num = i + 1
                    try:
                        weight = value['weight']
                        weight = int(weight)
                        if weight < 1 or weight > 15:
                            reasons.append('invalid weight "{}" in pool "{}" '
                                           'value {}'.format(weight, _id,
                                                             value_num))
                    except KeyError:
                        pass
                    except ValueError:
                        reasons.append('invalid weight "{}" in pool "{}" '
                                       'value {}'.format(weight, _id,
                                                         value_num))

                    try:
                        value = value['value']
                        reasons.extend(cls._value_type.validate(value,
                                                                cls._type))
                    except KeyError:
                        reasons.append('missing value in pool "{}" '
                                       'value {}'.format(_id, value_num))

                if len(values) == 1 and values[0].get('weight', 1) != 1:
                    reasons.append('pool "{}" has single value with '
                                   'weight!=1'.format(_id))

                fallback = pool.get('fallback', None)
                if fallback is not None:
                    if fallback in pools:
                        pools_seen_as_fallback.add(fallback)
                    else:
                        reasons.append('undefined fallback "{}" for pool "{}"'
                                       .format(fallback, _id))

                # Check for loops
                fallback = pools[_id].get('fallback', None)
                seen = [_id, fallback]
                while fallback is not None:
                    # See if there's a next fallback
                    fallback = pools.get(fallback, {}).get('fallback', None)
                    if fallback in seen:
                        loop = ' -> '.join(seen)
                        reasons.append('loop in pool fallbacks: {}'
                                       .format(loop))
                        # exit the loop
                        break
                    seen.append(fallback)

        try:
            rules = data['dynamic']['rules']
        except KeyError:
            rules = []

        if not isinstance(rules, (list, tuple)):
            reasons.append('rules must be a list')
        elif not rules:
            reasons.append('missing rules')
        else:
            seen_default = False

            for i, rule in enumerate(rules):
                rule_num = i + 1
                try:
                    pool = rule['pool']
                except KeyError:
                    reasons.append('rule {} missing pool'.format(rule_num))
                    continue

                try:
                    geos = rule['geos']
                except KeyError:
                    geos = []

                if not isinstance(pool, string_types):
                    reasons.append('rule {} invalid pool "{}"'
                                   .format(rule_num, pool))
                else:
                    if pool not in pools:
                        reasons.append('rule {} undefined pool "{}"'
                                       .format(rule_num, pool))
                    elif pool in pools_seen and geos:
                        reasons.append('rule {} invalid, target pool "{}" '
                                       'reused'.format(rule_num, pool))
                    pools_seen.add(pool)

                if not geos:
                    if seen_default:
                        reasons.append('rule {} duplicate default'
                                       .format(rule_num))
                    seen_default = True

                if not isinstance(geos, (list, tuple)):
                    reasons.append('rule {} geos must be a list'
                                   .format(rule_num))
                else:
                    for geo in geos:
                        reasons.extend(GeoCodes.validate(geo, 'rule {} '
                                                         .format(rule_num)))

        unused = pools_exist - pools_seen - pools_seen_as_fallback
        if unused:
            unused = '", "'.join(sorted(unused))
            reasons.append('unused pools: "{}"'.format(unused))

        return reasons

    def __init__(self, zone, name, data, *args, **kwargs):
        super(_DynamicMixin, self).__init__(zone, name, data, *args,
                                            **kwargs)

        self.dynamic = {}

        if 'dynamic' not in data:
            return

        # pools
        try:
            pools = dict(data['dynamic']['pools'])
        except:
            pools = {}

        for _id, pool in sorted(pools.items()):
            pools[_id] = _DynamicPool(_id, pool)

        # rules
        try:
            rules = list(data['dynamic']['rules'])
        except:
            rules = []

        parsed = []
        for i, rule in enumerate(rules):
            parsed.append(_DynamicRule(i, rule))

        # dynamic
        self.dynamic = _Dynamic(pools, parsed)

    def _data(self):
        ret = super(_DynamicMixin, self)._data()
        if self.dynamic:
            ret['dynamic'] = self.dynamic._data()
        return ret

    def changes(self, other, target):
        if target.SUPPORTS_DYNAMIC:
            if self.dynamic != other.dynamic:
                return Update(self, other)
        return super(_DynamicMixin, self).changes(other, target)

    def __repr__(self):
        # TODO: improve this whole thing, we need multi-line...
        if self.dynamic:
            # TODO: this hack can't going to cut it, as part of said
            # improvements the value types should deal with serializing their
            # value
            try:
                values = self.values
            except AttributeError:
                values = self.value

            return '<{} {} {}, {}, {}, {}>'.format(self.__class__.__name__,
                                                   self._type, self.ttl,
                                                   self.fqdn, values,
                                                   self.dynamic)
        return super(_DynamicMixin, self).__repr__()


class _IpList(object):

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        if len(data) == 0:
            return ['missing value(s)']
        reasons = []
        for value in data:
            if value == '':
                reasons.append('empty value')
            elif value is None:
                reasons.append('missing value(s)')
            else:
                try:
                    cls._address_type(text_type(value))
                except Exception:
                    reasons.append('invalid {} address "{}"'
                                   .format(cls._address_name, value))
        return reasons

    @classmethod
    def process(cls, values):
        # Translating None into '' so that the list will be sortable in
        # python3, get everything to str first
        values = [text_type(v) if v is not None else '' for v in values]
        # Now round trip all non-'' through the address type and back to a str
        # to normalize the address representation.
        return [text_type(cls._address_type(v)) if v != '' else ''
                for v in values]


class Ipv4List(_IpList):
    _address_name = 'IPv4'
    _address_type = IPv4Address


class Ipv6List(_IpList):
    _address_name = 'IPv6'
    _address_type = IPv6Address


class _TargetValue(object):

    @classmethod
    def validate(cls, data, _type):
        reasons = []
        if data == '':
            reasons.append('empty value')
        elif not data:
            reasons.append('missing value')
        # NOTE: FQDN complains if the data it receives isn't a str, it doesn't
        # allow unicode... This is likely specific to 2.7
        elif not FQDN(str(data), allow_underscores=True).is_valid:
            reasons.append('{} value "{}" is not a valid FQDN'
                           .format(_type, data))
        elif not data.endswith('.'):
            reasons.append('{} value "{}" missing trailing .'
                           .format(_type, data))
        return reasons

    @classmethod
    def process(self, value):
        if value:
            return value.lower()
        return value


class CnameValue(_TargetValue):
    pass


class DnameValue(_TargetValue):
    pass


class ARecord(_DynamicMixin, _GeoMixin, Record):
    _type = 'A'
    _value_type = Ipv4List


class AaaaRecord(_DynamicMixin, _GeoMixin, Record):
    _type = 'AAAA'
    _value_type = Ipv6List


class AliasValue(_TargetValue):
    pass


class AliasRecord(_ValueMixin, Record):
    _type = 'ALIAS'
    _value_type = AliasValue

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = []
        if name != '':
            reasons.append('non-root ALIAS not allowed')
        reasons.extend(super(AliasRecord, cls).validate(name, fqdn, data))
        return reasons


class CaaValue(EqualityTupleMixin):
    # https://tools.ietf.org/html/rfc6844#page-5

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            try:
                flags = int(value.get('flags', 0))
                if flags < 0 or flags > 255:
                    reasons.append('invalid flags "{}"'.format(flags))
            except ValueError:
                reasons.append('invalid flags "{}"'.format(value['flags']))

            if 'tag' not in value:
                reasons.append('missing tag')
            if 'value' not in value:
                reasons.append('missing value')
        return reasons

    @classmethod
    def process(cls, values):
        return [CaaValue(v) for v in values]

    def __init__(self, value):
        self.flags = int(value.get('flags', 0))
        self.tag = value['tag']
        self.value = value['value']

    @property
    def data(self):
        return {
            'flags': self.flags,
            'tag': self.tag,
            'value': self.value,
        }

    def _equality_tuple(self):
        return (self.flags, self.tag, self.value)

    def __repr__(self):
        return '{} {} "{}"'.format(self.flags, self.tag, self.value)


class CaaRecord(_ValuesMixin, Record):
    _type = 'CAA'
    _value_type = CaaValue


class CnameRecord(_DynamicMixin, _ValueMixin, Record):
    _type = 'CNAME'
    _value_type = CnameValue

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = []
        if name == '':
            reasons.append('root CNAME not allowed')
        reasons.extend(super(CnameRecord, cls).validate(name, fqdn, data))
        return reasons


class DnameRecord(_DynamicMixin, _ValueMixin, Record):
    _type = 'DNAME'
    _value_type = DnameValue


class LocValue(EqualityTupleMixin):
    # TODO: work out how to do defaults per RFC

    @classmethod
    def validate(cls, data, _type):
        int_keys = [
            'lat_degrees',
            'lat_minutes',
            'long_degrees',
            'long_minutes',
        ]

        float_keys = [
            'lat_seconds',
            'long_seconds',
            'altitude',
            'size',
            'precision_horz',
            'precision_vert',
        ]

        direction_keys = [
            'lat_direction',
            'long_direction',
        ]

        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            for key in int_keys:
                try:
                    int(value[key])
                    if (
                        (
                            key == 'lat_degrees' and
                            not 0 <= int(value[key]) <= 90
                        ) or (
                            key == 'long_degrees' and
                            not 0 <= int(value[key]) <= 180
                        ) or (
                            key in ['lat_minutes', 'long_minutes'] and
                            not 0 <= int(value[key]) <= 59
                        )
                    ):
                        reasons.append('invalid value for {} "{}"'
                                       .format(key, value[key]))
                except KeyError:
                    reasons.append('missing {}'.format(key))
                except ValueError:
                    reasons.append('invalid {} "{}"'
                                   .format(key, value[key]))

            for key in float_keys:
                try:
                    float(value[key])
                    if (
                        (
                            key in ['lat_seconds', 'long_seconds'] and
                            not 0 <= float(value[key]) <= 59.999
                        ) or (
                            key == 'altitude' and
                            not -100000.00 <= float(value[key]) <= 42849672.95
                        ) or (
                            key in ['size',
                                    'precision_horz',
                                    'precision_vert'] and
                            not 0 <= float(value[key]) <= 90000000.00
                        )
                    ):
                        reasons.append('invalid value for {} "{}"'
                                       .format(key, value[key]))
                except KeyError:
                    reasons.append('missing {}'.format(key))
                except ValueError:
                    reasons.append('invalid {} "{}"'
                                   .format(key, value[key]))

            for key in direction_keys:
                try:
                    str(value[key])
                    if (
                        key == 'lat_direction' and
                        value[key] not in ['N', 'S']
                    ):
                        reasons.append('invalid direction for {} "{}"'
                                       .format(key, value[key]))
                    if (
                        key == 'long_direction' and
                        value[key] not in ['E', 'W']
                    ):
                        reasons.append('invalid direction for {} "{}"'
                                       .format(key, value[key]))
                except KeyError:
                    reasons.append('missing {}'.format(key))
        return reasons

    @classmethod
    def process(cls, values):
        return [LocValue(v) for v in values]

    def __init__(self, value):
        self.lat_degrees = int(value['lat_degrees'])
        self.lat_minutes = int(value['lat_minutes'])
        self.lat_seconds = float(value['lat_seconds'])
        self.lat_direction = value['lat_direction'].upper()
        self.long_degrees = int(value['long_degrees'])
        self.long_minutes = int(value['long_minutes'])
        self.long_seconds = float(value['long_seconds'])
        self.long_direction = value['long_direction'].upper()
        self.altitude = float(value['altitude'])
        self.size = float(value['size'])
        self.precision_horz = float(value['precision_horz'])
        self.precision_vert = float(value['precision_vert'])

    @property
    def data(self):
        return {
            'lat_degrees': self.lat_degrees,
            'lat_minutes': self.lat_minutes,
            'lat_seconds': self.lat_seconds,
            'lat_direction': self.lat_direction,
            'long_degrees': self.long_degrees,
            'long_minutes': self.long_minutes,
            'long_seconds': self.long_seconds,
            'long_direction': self.long_direction,
            'altitude': self.altitude,
            'size': self.size,
            'precision_horz': self.precision_horz,
            'precision_vert': self.precision_vert,
        }

    def __hash__(self):
        return hash((
            self.lat_degrees,
            self.lat_minutes,
            self.lat_seconds,
            self.lat_direction,
            self.long_degrees,
            self.long_minutes,
            self.long_seconds,
            self.long_direction,
            self.altitude,
            self.size,
            self.precision_horz,
            self.precision_vert,
        ))

    def _equality_tuple(self):
        return (
            self.lat_degrees,
            self.lat_minutes,
            self.lat_seconds,
            self.lat_direction,
            self.long_degrees,
            self.long_minutes,
            self.long_seconds,
            self.long_direction,
            self.altitude,
            self.size,
            self.precision_horz,
            self.precision_vert,
        )

    def __repr__(self):
        loc_format = "'{0} {1} {2:.3f} {3} " + \
            "{4} {5} {6:.3f} {7} " + \
            "{8:.2f}m {9:.2f}m {10:.2f}m {11:.2f}m'"
        return loc_format.format(
            self.lat_degrees,
            self.lat_minutes,
            self.lat_seconds,
            self.lat_direction,
            self.long_degrees,
            self.long_minutes,
            self.long_seconds,
            self.long_direction,
            self.altitude,
            self.size,
            self.precision_horz,
            self.precision_vert,
        )


class LocRecord(_ValuesMixin, Record):
    _type = 'LOC'
    _value_type = LocValue


class MxValue(EqualityTupleMixin):

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            try:
                try:
                    int(value['preference'])
                except KeyError:
                    int(value['priority'])
            except KeyError:
                reasons.append('missing preference')
            except ValueError:
                reasons.append('invalid preference "{}"'
                               .format(value['preference']))
            exchange = None
            try:
                exchange = value.get('exchange', None) or value['value']
                if not exchange.endswith('.'):
                    reasons.append('MX value "{}" missing trailing .'
                                   .format(exchange))
            except KeyError:
                reasons.append('missing exchange')
        return reasons

    @classmethod
    def process(cls, values):
        return [MxValue(v) for v in values]

    def __init__(self, value):
        # RFC1035 says preference, half the providers use priority
        try:
            preference = value['preference']
        except KeyError:
            preference = value['priority']
        self.preference = int(preference)
        # UNTIL 1.0 remove value fallback
        try:
            exchange = value['exchange']
        except KeyError:
            exchange = value['value']
        self.exchange = exchange.lower()

    @property
    def data(self):
        return {
            'preference': self.preference,
            'exchange': self.exchange,
        }

    def __hash__(self):
        return hash((self.preference, self.exchange))

    def _equality_tuple(self):
        return (self.preference, self.exchange)

    def __repr__(self):
        return "'{} {}'".format(self.preference, self.exchange)


class MxRecord(_ValuesMixin, Record):
    _type = 'MX'
    _value_type = MxValue


class NaptrValue(EqualityTupleMixin):
    VALID_FLAGS = ('S', 'A', 'U', 'P')

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            try:
                int(value['order'])
            except KeyError:
                reasons.append('missing order')
            except ValueError:
                reasons.append('invalid order "{}"'.format(value['order']))
            try:
                int(value['preference'])
            except KeyError:
                reasons.append('missing preference')
            except ValueError:
                reasons.append('invalid preference "{}"'
                               .format(value['preference']))
            try:
                flags = value['flags']
                if flags not in cls.VALID_FLAGS:
                    reasons.append('unrecognized flags "{}"'.format(flags))
            except KeyError:
                reasons.append('missing flags')

            # TODO: validate these... they're non-trivial
            for k in ('service', 'regexp', 'replacement'):
                if k not in value:
                    reasons.append('missing {}'.format(k))

        return reasons

    @classmethod
    def process(cls, values):
        return [NaptrValue(v) for v in values]

    def __init__(self, value):
        self.order = int(value['order'])
        self.preference = int(value['preference'])
        self.flags = value['flags']
        self.service = value['service']
        self.regexp = value['regexp']
        self.replacement = value['replacement']

    @property
    def data(self):
        return {
            'order': self.order,
            'preference': self.preference,
            'flags': self.flags,
            'service': self.service,
            'regexp': self.regexp,
            'replacement': self.replacement,
        }

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (self.order, self.preference, self.flags, self.service,
                self.regexp, self.replacement)

    def __repr__(self):
        flags = self.flags if self.flags is not None else ''
        service = self.service if self.service is not None else ''
        regexp = self.regexp if self.regexp is not None else ''
        return "'{} {} \"{}\" \"{}\" \"{}\" {}'" \
            .format(self.order, self.preference, flags, service, regexp,
                    self.replacement)


class NaptrRecord(_ValuesMixin, Record):
    _type = 'NAPTR'
    _value_type = NaptrValue


class _NsValue(object):

    @classmethod
    def validate(cls, data, _type):
        if not data:
            return ['missing value(s)']
        elif not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            if not value.endswith('.'):
                reasons.append('NS value "{}" missing trailing .'
                               .format(value))
        return reasons

    @classmethod
    def process(cls, values):
        return values


class NsRecord(_ValuesMixin, Record):
    _type = 'NS'
    _value_type = _NsValue


class PtrValue(_TargetValue):

    @classmethod
    def validate(cls, values, _type):
        if not isinstance(values, list):
            values = [values]

        reasons = []

        if not values:
            reasons.append('missing values')

        for value in values:
            reasons.extend(super(PtrValue, cls).validate(value, _type))

        return reasons

    @classmethod
    def process(cls, values):
        return [super(PtrValue, cls).process(v) for v in values]


class PtrRecord(_ValuesMixin, Record):
    _type = 'PTR'
    _value_type = PtrValue

    # This is for backward compatibility with providers that don't support
    # multi-value PTR records.
    @property
    def value(self):
        return self.values[0]


class SshfpValue(EqualityTupleMixin):
    VALID_ALGORITHMS = (1, 2, 3, 4)
    VALID_FINGERPRINT_TYPES = (1, 2)

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            try:
                algorithm = int(value['algorithm'])
                if algorithm not in cls.VALID_ALGORITHMS:
                    reasons.append('unrecognized algorithm "{}"'
                                   .format(algorithm))
            except KeyError:
                reasons.append('missing algorithm')
            except ValueError:
                reasons.append('invalid algorithm "{}"'
                               .format(value['algorithm']))
            try:
                fingerprint_type = int(value['fingerprint_type'])
                if fingerprint_type not in cls.VALID_FINGERPRINT_TYPES:
                    reasons.append('unrecognized fingerprint_type "{}"'
                                   .format(fingerprint_type))
            except KeyError:
                reasons.append('missing fingerprint_type')
            except ValueError:
                reasons.append('invalid fingerprint_type "{}"'
                               .format(value['fingerprint_type']))
            if 'fingerprint' not in value:
                reasons.append('missing fingerprint')
        return reasons

    @classmethod
    def process(cls, values):
        return [SshfpValue(v) for v in values]

    def __init__(self, value):
        self.algorithm = int(value['algorithm'])
        self.fingerprint_type = int(value['fingerprint_type'])
        self.fingerprint = value['fingerprint']

    @property
    def data(self):
        return {
            'algorithm': self.algorithm,
            'fingerprint_type': self.fingerprint_type,
            'fingerprint': self.fingerprint,
        }

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (self.algorithm, self.fingerprint_type, self.fingerprint)

    def __repr__(self):
        return "'{} {} {}'".format(self.algorithm, self.fingerprint_type,
                                   self.fingerprint)


class SshfpRecord(_ValuesMixin, Record):
    _type = 'SSHFP'
    _value_type = SshfpValue


class _ChunkedValuesMixin(_ValuesMixin):
    CHUNK_SIZE = 255
    _unescaped_semicolon_re = re.compile(r'\w;')

    def chunked_value(self, value):
        value = value.replace('"', '\\"')
        vs = [value[i:i + self.CHUNK_SIZE]
              for i in range(0, len(value), self.CHUNK_SIZE)]
        vs = '" "'.join(vs)
        return '"{}"'.format(vs)

    @property
    def chunked_values(self):
        values = []
        for v in self.values:
            values.append(self.chunked_value(v))
        return values


class _ChunkedValue(object):
    _unescaped_semicolon_re = re.compile(r'\w;')

    @classmethod
    def validate(cls, data, _type):
        if not data:
            return ['missing value(s)']
        elif not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            if cls._unescaped_semicolon_re.search(value):
                reasons.append('unescaped ; in "{}"'.format(value))
        return reasons

    @classmethod
    def process(cls, values):
        ret = []
        for v in values:
            if v and v[0] == '"':
                v = v[1:-1]
            ret.append(v.replace('" "', ''))
        return ret


class SpfRecord(_ChunkedValuesMixin, Record):
    _type = 'SPF'
    _value_type = _ChunkedValue


class SrvValue(EqualityTupleMixin):

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            # TODO: validate algorithm and fingerprint_type values
            try:
                int(value['priority'])
            except KeyError:
                reasons.append('missing priority')
            except ValueError:
                reasons.append('invalid priority "{}"'
                               .format(value['priority']))
            try:
                int(value['weight'])
            except KeyError:
                reasons.append('missing weight')
            except ValueError:
                reasons.append('invalid weight "{}"'.format(value['weight']))
            try:
                int(value['port'])
            except KeyError:
                reasons.append('missing port')
            except ValueError:
                reasons.append('invalid port "{}"'.format(value['port']))
            try:
                if not value['target'].endswith('.'):
                    reasons.append('SRV value "{}" missing trailing .'
                                   .format(value['target']))
            except KeyError:
                reasons.append('missing target')
        return reasons

    @classmethod
    def process(cls, values):
        return [SrvValue(v) for v in values]

    def __init__(self, value):
        self.priority = int(value['priority'])
        self.weight = int(value['weight'])
        self.port = int(value['port'])
        self.target = value['target'].lower()

    @property
    def data(self):
        return {
            'priority': self.priority,
            'weight': self.weight,
            'port': self.port,
            'target': self.target,
        }

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (self.priority, self.weight, self.port, self.target)

    def __repr__(self):
        return "'{} {} {} {}'".format(self.priority, self.weight, self.port,
                                      self.target)


class SrvRecord(_ValuesMixin, Record):
    _type = 'SRV'
    _value_type = SrvValue
    _name_re = re.compile(r'^(\*|_[^\.]+)\.[^\.]+')

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = []
        if not cls._name_re.match(name):
            reasons.append('invalid name for SRV record')
        reasons.extend(super(SrvRecord, cls).validate(name, fqdn, data))
        return reasons


class _TxtValue(_ChunkedValue):
    pass


class TxtRecord(_ChunkedValuesMixin, Record):
    _type = 'TXT'
    _value_type = _TxtValue


class UrlfwdValue(EqualityTupleMixin):
    VALID_CODES = (301, 302)
    VALID_MASKS = (0, 1, 2)
    VALID_QUERY = (0, 1)

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            try:
                code = int(value['code'])
                if code not in cls.VALID_CODES:
                    reasons.append('unrecognized return code "{}"'
                                   .format(code))
            except KeyError:
                reasons.append('missing code')
            except ValueError:
                reasons.append('invalid return code "{}"'
                               .format(value['code']))
            try:
                masking = int(value['masking'])
                if masking not in cls.VALID_MASKS:
                    reasons.append('unrecognized masking setting "{}"'
                                   .format(masking))
            except KeyError:
                reasons.append('missing masking')
            except ValueError:
                reasons.append('invalid masking setting "{}"'
                               .format(value['masking']))
            try:
                query = int(value['query'])
                if query not in cls.VALID_QUERY:
                    reasons.append('unrecognized query setting "{}"'
                                   .format(query))
            except KeyError:
                reasons.append('missing query')
            except ValueError:
                reasons.append('invalid query setting "{}"'
                               .format(value['query']))
            for k in ('path', 'target'):
                if k not in value:
                    reasons.append('missing {}'.format(k))
        return reasons

    @classmethod
    def process(cls, values):
        return [UrlfwdValue(v) for v in values]

    def __init__(self, value):
        self.path = value['path']
        self.target = value['target']
        self.code = int(value['code'])
        self.masking = int(value['masking'])
        self.query = int(value['query'])

    @property
    def data(self):
        return {
            'path': self.path,
            'target': self.target,
            'code': self.code,
            'masking': self.masking,
            'query': self.query,
        }

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (self.path, self.target, self.code, self.masking, self.query)

    def __repr__(self):
        return '"{}" "{}" {} {} {}'.format(self.path, self.target, self.code,
                                           self.masking, self.query)


class UrlfwdRecord(_ValuesMixin, Record):
    _type = 'URLFWD'
    _value_type = UrlfwdValue
