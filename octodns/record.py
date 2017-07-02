#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from ipaddress import IPv4Address, IPv6Address
from logging import getLogger
import re


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
                # cert
                'CNAME': CnameRecord,
                # dhcid
                # dname
                # dnskey
                # ds
                # ipseckey
                # key
                # kx
                # loc
                'MX': MxRecord,
                'NAPTR': NaptrRecord,
                'NS': NsRecord,
                # nsap
                'PTR': PtrRecord,
                # px
                # rp
                # soa - would it even make sense?
                'SPF': SpfRecord,
                'SRV': SrvRecord,
                'SSHFP': SshfpRecord,
                'TXT': TxtRecord,
                # url
            }[_type]
        except KeyError:
            raise Exception('Unknown record type: "{}"'.format(_type))
        reasons = _class.validate(name, data)
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
        return reasons

    def __init__(self, zone, name, data, source=None):
        self.log.debug('__init__: zone.name=%s, type=%11s, name=%s', zone.name,
                       self.__class__.__name__, name)
        self.zone = zone
        # force everything lower-case just to be safe
        self.name = str(name).lower() if name else name
        self.source = source
        self.ttl = int(data['ttl'])

        octodns = data.get('octodns', {})
        self.ignored = octodns.get('ignored', False)

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

    def changes(self, other, target):
        # We're assuming we have the same name and type if we're being compared
        if self.ttl != other.ttl:
            return Update(self, other)

    # NOTE: we're using __hash__ and __cmp__ methods that consider Records
    # equivalent if they have the same name & _type. Values are ignored. This
    # is usful when computing diffs/changes.

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
        self.values = values

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
        values = []
        try:
            values = data['values']
        except KeyError:
            try:
                values = [data['value']]
            except KeyError:
                reasons.append('missing value(s)')

        for value in values:
            reasons.extend(cls._validate_value(value))

        return reasons

    def __init__(self, zone, name, data, source=None):
        super(_ValuesMixin, self).__init__(zone, name, data, source=source)
        try:
            values = data['values']
        except KeyError:
            values = [data['value']]
        self.values = sorted(self._process_values(values))

    def changes(self, other, target):
        if self.values != other.values:
            return Update(self, other)
        return super(_ValuesMixin, self).changes(other, target)

    def _data(self):
        ret = super(_ValuesMixin, self)._data()
        if len(self.values) > 1:
            ret['values'] = [getattr(v, 'data', v) for v in self.values]
        else:
            v = self.values[0]
            ret['value'] = getattr(v, 'data', v)
        return ret

    def __repr__(self):
        values = "['{}']".format("', '".join([str(v) for v in self.values]))
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
            # TODO: validate legal codes
            for code, values in geo.items():
                reasons.extend(GeoValue._validate_geo(code))
                for value in values:
                    reasons.extend(cls._validate_value(value))
        except KeyError:
            pass
        return reasons

    # TODO: support 'value' as well
    # TODO: move away from "data" hash to strict params, it's kind of leaking
    # the yaml implementation into here and then forcing it back out into
    # non-yaml providers during input
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


class ARecord(_GeoMixin, Record):
    _type = 'A'

    @classmethod
    def _validate_value(self, value):
        reasons = []
        try:
            IPv4Address(unicode(value))
        except Exception:
            reasons.append('invalid ip address "{}"'.format(value))
        return reasons

    def _process_values(self, values):
        return values


class AaaaRecord(_GeoMixin, Record):
    _type = 'AAAA'

    @classmethod
    def _validate_value(self, value):
        reasons = []
        try:
            IPv6Address(unicode(value))
        except Exception:
            reasons.append('invalid ip address "{}"'.format(value))
        return reasons

    def _process_values(self, values):
        return values


class _ValueMixin(object):

    @classmethod
    def validate(cls, name, data):
        reasons = super(_ValueMixin, cls).validate(name, data)
        value = None
        try:
            value = data['value']
        except KeyError:
            reasons.append('missing value')
        if value:
            reasons.extend(cls._validate_value(value))
        return reasons

    def __init__(self, zone, name, data, source=None):
        super(_ValueMixin, self).__init__(zone, name, data, source=source)
        self.value = self._process_value(data['value'])

    def changes(self, other, target):
        if self.value != other.value:
            return Update(self, other)
        return super(_ValueMixin, self).changes(other, target)

    def _data(self):
        ret = super(_ValueMixin, self)._data()
        ret['value'] = getattr(self.value, 'data', self.value)
        return ret

    def __repr__(self):
        return '<{} {} {}, {}, {}>'.format(self.__class__.__name__,
                                           self._type, self.ttl,
                                           self.fqdn, self.value)


class AliasRecord(_ValueMixin, Record):
    _type = 'ALIAS'

    @classmethod
    def _validate_value(self, value):
        reasons = []
        if not value.endswith('.'):
            reasons.append('missing trailing .')
        return reasons

    def _process_value(self, value):
        return value


class CnameRecord(_ValueMixin, Record):
    _type = 'CNAME'

    @classmethod
    def validate(cls, name, data):
        reasons = []
        if name == '':
            reasons.append('root CNAME not allowed')
        reasons.extend(super(CnameRecord, cls).validate(name, data))
        return reasons

    @classmethod
    def _validate_value(cls, value):
        reasons = []
        if not value.endswith('.'):
            reasons.append('missing trailing .')
        return reasons

    def _process_value(self, value):
        return value


class MxValue(object):

    @classmethod
    def _validate_value(cls, value):
        reasons = []
        try:
            int(value.get('preference', None) or value['priority'])
        except KeyError:
            reasons.append('missing preference')
        except ValueError:
            reasons.append('invalid preference "{}"'
                           .format(value['preference']))
        exchange = None
        try:
            exchange = value.get('exchange', None) or value['value']
            if not exchange.endswith('.'):
                reasons.append('missing trailing .')
        except KeyError:
            reasons.append('missing exchange')
        return reasons

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
        self.exchange = exchange

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

    @classmethod
    def _validate_value(cls, value):
        return MxValue._validate_value(value)

    def _process_values(self, values):
        return [MxValue(v) for v in values]


class NaptrValue(object):
    VALID_FLAGS = ('S', 'A', 'U', 'P')

    @classmethod
    def _validate_value(cls, data):
        reasons = []
        try:
            int(data['order'])
        except KeyError:
            reasons.append('missing order')
        except ValueError:
            reasons.append('invalid order "{}"'.format(data['order']))
        try:
            int(data['preference'])
        except KeyError:
            reasons.append('missing preference')
        except ValueError:
            reasons.append('invalid preference "{}"'
                           .format(data['preference']))
        try:
            flags = data['flags']
            if flags not in cls.VALID_FLAGS:
                reasons.append('unrecognized flags "{}"'.format(flags))
        except KeyError:
            reasons.append('missing flags')

        # TODO: validate these... they're non-trivial
        for k in ('service', 'regexp', 'replacement'):
            if k not in data:
                reasons.append('missing {}'.format(k))
        return reasons

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

    @classmethod
    def _validate_value(cls, value):
        return NaptrValue._validate_value(value)

    def _process_values(self, values):
        return [NaptrValue(v) for v in values]


class NsRecord(_ValuesMixin, Record):
    _type = 'NS'

    @classmethod
    def _validate_value(cls, value):
        reasons = []
        if not value.endswith('.'):
            reasons.append('missing trailing .')
        return reasons

    def _process_values(self, values):
        return values


class PtrRecord(_ValueMixin, Record):
    _type = 'PTR'

    @classmethod
    def _validate_value(cls, value):
        reasons = []
        if not value.endswith('.'):
            reasons.append('missing trailing .')
        return reasons

    def _process_value(self, value):
        return value


class SshfpValue(object):
    VALID_ALGORITHMS = (1, 2)
    VALID_FINGERPRINT_TYPES = (1,)

    @classmethod
    def _validate_value(cls, value):
        reasons = []
        try:
            algorithm = int(value['algorithm'])
            if algorithm not in cls.VALID_ALGORITHMS:
                reasons.append('unrecognized algorithm "{}"'.format(algorithm))
        except KeyError:
            reasons.append('missing algorithm')
        except ValueError:
            reasons.append('invalid algorithm "{}"'.format(value['algorithm']))
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

    @classmethod
    def _validate_value(cls, value):
        return SshfpValue._validate_value(value)

    def _process_values(self, values):
        return [SshfpValue(v) for v in values]


_unescaped_semicolon_re = re.compile(r'\w;')


class SpfRecord(_ValuesMixin, Record):
    _type = 'SPF'

    @classmethod
    def _validate_value(cls, value):
        if _unescaped_semicolon_re.search(value):
            return ['unescaped ;']
        return []

    def _process_values(self, values):
        return values


class SrvValue(object):

    @classmethod
    def _validate_value(self, value):
        reasons = []
        # TODO: validate algorithm and fingerprint_type values
        try:
            int(value['priority'])
        except KeyError:
            reasons.append('missing priority')
        except ValueError:
            reasons.append('invalid priority "{}"'.format(value['priority']))
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
                reasons.append('missing trailing .')
        except KeyError:
            reasons.append('missing target')
        return reasons

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
    _name_re = re.compile(r'^_[^\.]+\.[^\.]+')

    @classmethod
    def validate(cls, name, data):
        reasons = []
        if not cls._name_re.match(name):
            reasons.append('invalid name')
        reasons.extend(super(SrvRecord, cls).validate(name, data))
        return reasons

    @classmethod
    def _validate_value(cls, value):
        return SrvValue._validate_value(value)

    def _process_values(self, values):
        return [SrvValue(v) for v in values]


class TxtRecord(_ValuesMixin, Record):
    _type = 'TXT'

    @classmethod
    def _validate_value(cls, value):
        if _unescaped_semicolon_re.search(value):
            return ['unescaped ;']
        return []

    def _process_values(self, values):
        return values
