#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from ipaddress import IPv4Address, IPv6Address
from logging import getLogger
import re

from .geo import GeoCodes


class Change(object):

    def __init__(self, existing, new):
        self.existing = existing
        self.new = new

    @property
    def record(self):
        'Returns new if we have one, existing otherwise'
        return self.new or self.existing


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


class Record(object):
    log = getLogger('Record')

    @classmethod
    def new(cls, zone, name, data, source=None, lenient=False):
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
                'MX': MxRecord,
                'NAPTR': NaptrRecord,
                'NS': NsRecord,
                'PTR': PtrRecord,
                'SPF': SpfRecord,
                'SRV': SrvRecord,
                'SSHFP': SshfpRecord,
                'TXT': TxtRecord,
            }[_type]
        except KeyError:
            raise Exception('Unknown record type: "{}"'.format(_type))
        reasons = _class.validate(name, data)
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
    def validate(cls, name, data):
        reasons = []
        try:
            ttl = int(data['ttl'])
            if ttl < 0:
                reasons.append('invalid ttl')
        except KeyError:
            reasons.append('missing ttl')
        try:
            if data['octodns']['healthcheck']['protocol'] \
               not in ('HTTP', 'HTTPS'):
                reasons.append('invalid healthcheck protocol')
        except KeyError:
            pass
        return reasons

    def __init__(self, zone, name, data, source=None):
        self.log.debug('__init__: zone.name=%s, type=%11s, name=%s', zone.name,
                       self.__class__.__name__, name)
        self.zone = zone
        # force everything lower-case just to be safe
        self.name = unicode(name).lower() if name else name
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

    @property
    def healthcheck_host(self):
        try:
            return self._octodns['healthcheck']['host']
        except KeyError:
            return self.fqdn[:-1]

    @property
    def healthcheck_path(self):
        try:
            return self._octodns['healthcheck']['path']
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

    # NOTE: we're using __hash__ and __cmp__ methods that consider Records
    # equivalent if they have the same name & _type. Values are ignored. This
    # is useful when computing diffs/changes.

    def __hash__(self):
        return '{}:{}'.format(self.name, self._type).__hash__()

    def __cmp__(self, other):
        a = '{}:{}'.format(self.name, self._type)
        b = '{}:{}'.format(other.name, other._type)
        return cmp(a, b)

    def __repr__(self):
        # Make sure this is always overridden
        raise NotImplementedError('Abstract base class, __repr__ required')


class GeoValue(object):
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

    def __cmp__(self, other):
        return 0 if (self.continent_code == other.continent_code and
                     self.country_code == other.country_code and
                     self.subdivision_code == other.subdivision_code and
                     self.values == other.values) else 1

    def __repr__(self):
        return "'Geo {} {} {} {}'".format(self.continent_code,
                                          self.country_code,
                                          self.subdivision_code, self.values)


class _ValuesMixin(object):

    @classmethod
    def validate(cls, name, data):
        reasons = super(_ValuesMixin, cls).validate(name, data)

        values = data.get('values', data.get('value', []))

        reasons.extend(cls._value_type.validate(values, cls._type))

        return reasons

    def __init__(self, zone, name, data, source=None):
        super(_ValuesMixin, self).__init__(zone, name, data, source=source)
        try:
            values = data['values']
        except KeyError:
            values = [data['value']]
        # TODO: should we natsort values?
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
        values = "['{}']".format("', '".join([unicode(v)
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
    def validate(cls, name, data):
        reasons = super(_GeoMixin, cls).validate(name, data)
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
    def validate(cls, name, data):
        reasons = super(_ValueMixin, cls).validate(name, data)
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

    def __init__(self, _id, data):
        self._id = _id

        values = [
            {
                'value': d['value'],
                'weight': d.get('weight', 1),
            } for d in data['values']
        ]
        values.sort(key=lambda d: d['value'])

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
    def validate(cls, name, data):
        reasons = super(_DynamicMixin, cls).validate(name, data)

        if 'dynamic' not in data:
            return reasons
        elif 'geo' in data:
            reasons.append('"dynamic" record with "geo" content')

        try:
            pools = data['dynamic']['pools']
        except KeyError:
            pools = {}

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

                fallback = pool.get('fallback', None)
                if fallback is not None and fallback not in pools:
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

            # TODO: don't allow 'default' as a pool name, reserved
            # TODO: warn or error on unused pools?
            for i, rule in enumerate(rules):
                rule_num = i + 1
                try:
                    pool = rule['pool']
                except KeyError:
                    reasons.append('rule {} missing pool'.format(rule_num))
                    continue

                if not isinstance(pool, basestring):
                    reasons.append('rule {} invalid pool "{}"'
                                   .format(rule_num, pool))
                elif pool not in pools:
                    reasons.append('rule {} undefined pool "{}"'
                                   .format(rule_num, pool))

                try:
                    geos = rule['geos']
                except KeyError:
                    geos = []
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
            if value is '':
                reasons.append('empty value')
            elif value is None:
                reasons.append('missing value(s)')
            else:
                try:
                    cls._address_type(unicode(value))
                except Exception:
                    reasons.append('invalid {} address "{}"'
                                   .format(cls._address_name, value))
        return reasons

    @classmethod
    def process(cls, values):
        return values


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


class CaaValue(object):
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

    def __cmp__(self, other):
        if self.flags == other.flags:
            if self.tag == other.tag:
                return cmp(self.value, other.value)
            return cmp(self.tag, other.tag)
        return cmp(self.flags, other.flags)

    def __repr__(self):
        return '{} {} "{}"'.format(self.flags, self.tag, self.value)


class CaaRecord(_ValuesMixin, Record):
    _type = 'CAA'
    _value_type = CaaValue


class CnameRecord(_DynamicMixin, _ValueMixin, Record):
    _type = 'CNAME'
    _value_type = CnameValue

    @classmethod
    def validate(cls, name, data):
        reasons = []
        if name == '':
            reasons.append('root CNAME not allowed')
        reasons.extend(super(CnameRecord, cls).validate(name, data))
        return reasons


class MxValue(object):

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

    def __cmp__(self, other):
        if self.preference == other.preference:
            return cmp(self.exchange, other.exchange)
        return cmp(self.preference, other.preference)

    def __repr__(self):
        return "'{} {}'".format(self.preference, self.exchange)


class MxRecord(_ValuesMixin, Record):
    _type = 'MX'
    _value_type = MxValue


class NaptrValue(object):
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

    def __cmp__(self, other):
        if self.order != other.order:
            return cmp(self.order, other.order)
        elif self.preference != other.preference:
            return cmp(self.preference, other.preference)
        elif self.flags != other.flags:
            return cmp(self.flags, other.flags)
        elif self.service != other.service:
            return cmp(self.service, other.service)
        elif self.regexp != other.regexp:
            return cmp(self.regexp, other.regexp)
        return cmp(self.replacement, other.replacement)

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
    pass


class PtrRecord(_ValueMixin, Record):
    _type = 'PTR'
    _value_type = PtrValue


class SshfpValue(object):
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

    def __cmp__(self, other):
        if self.algorithm != other.algorithm:
            return cmp(self.algorithm, other.algorithm)
        elif self.fingerprint_type != other.fingerprint_type:
            return cmp(self.fingerprint_type, other.fingerprint_type)
        return cmp(self.fingerprint, other.fingerprint)

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


class SrvValue(object):

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

    def __cmp__(self, other):
        if self.priority != other.priority:
            return cmp(self.priority, other.priority)
        elif self.weight != other.weight:
            return cmp(self.weight, other.weight)
        elif self.port != other.port:
            return cmp(self.port, other.port)
        return cmp(self.target, other.target)

    def __repr__(self):
        return "'{} {} {} {}'".format(self.priority, self.weight, self.port,
                                      self.target)


class SrvRecord(_ValuesMixin, Record):
    _type = 'SRV'
    _value_type = SrvValue
    _name_re = re.compile(r'^_[^\.]+\.[^\.]+')

    @classmethod
    def validate(cls, name, data):
        reasons = []
        if not cls._name_re.match(name):
            reasons.append('invalid name')
        reasons.extend(super(SrvRecord, cls).validate(name, data))
        return reasons


class _TxtValue(_ChunkedValue):
    pass


class TxtRecord(_ChunkedValuesMixin, Record):
    _type = 'TXT'
    _value_type = _TxtValue
