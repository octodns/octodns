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


_unescaped_semicolon_re = re.compile(r'\w;')


class Record(object):
    log = getLogger('Record')

    @classmethod
    def new(cls, zone, name, data, source=None):
        try:
            _type = data['type']
        except KeyError:
            fqdn = '{}.{}'.format(name, zone.name) if name else zone.name
            raise Exception('Invalid record {}, missing type'.format(fqdn))
        try:
            _type = {
                'A': ARecord,
                'AAAA': AaaaRecord,
                # alias
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
        return _type(zone, name, data, source=source)

    def __init__(self, zone, name, data, source=None):
        self.log.debug('__init__: zone.name=%s, type=%11s, name=%s', zone.name,
                       self.__class__.__name__, name)
        self.zone = zone
        # force everything lower-case just to be safe
        self.name = str(name).lower() if name else name
        try:
            self.ttl = int(data['ttl'])
        except KeyError:
            raise Exception('Invalid record {}, missing ttl'.format(self.fqdn))
        self.source = source

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

    def __init__(self, geo, values):
        match = self.geo_re.match(geo)
        if not match:
            raise Exception('Invalid geo "{}"'.format(geo))
        self.code = geo
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

    def __init__(self, zone, name, data, source=None):
        super(_ValuesMixin, self).__init__(zone, name, data, source=source)
        try:
            self.values = sorted(self._process_values(data['values']))
        except KeyError:
            try:
                self.values = self._process_values([data['value']])
            except KeyError:
                raise Exception('Invalid record {}, missing value(s)'
                                .format(self.fqdn))

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
        return '<{} {} {}, {}, {}>'.format(self.__class__.__name__,
                                           self._type, self.ttl,
                                           self.fqdn, self.values)


class _GeoMixin(_ValuesMixin):
    '''
    Adds GeoDNS support to a record.

    Must be included before `Record`.
    '''

    # TODO: move away from "data" hash to strict params, it's kind of leaking
    # the yaml implementation into here and then forcing it back out into
    # non-yaml providers during input
    def __init__(self, zone, name, data, *args, **kwargs):
        super(_GeoMixin, self).__init__(zone, name, data, *args, **kwargs)
        try:
            self.geo = dict(data['geo'])
        except KeyError:
            self.geo = {}
        for k, vs in self.geo.items():
            vs = sorted(self._process_values(vs))
            self.geo[k] = GeoValue(k, vs)

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

    def _process_values(self, values):
        for ip in values:
            try:
                IPv4Address(unicode(ip))
            except Exception:
                raise Exception('Invalid record {}, value {} not a valid ip'
                                .format(self.fqdn, ip))
        return values


class AaaaRecord(_GeoMixin, Record):
    _type = 'AAAA'

    def _process_values(self, values):
        ret = []
        for ip in values:
            try:
                IPv6Address(unicode(ip))
                ret.append(ip.lower())
            except Exception:
                raise Exception('Invalid record {}, value {} not a valid ip'
                                .format(self.fqdn, ip))
        return ret


class _ValueMixin(object):

    def __init__(self, zone, name, data, source=None):
        super(_ValueMixin, self).__init__(zone, name, data, source=source)
        try:
            self.value = self._process_value(data['value'])
        except KeyError:
            raise Exception('Invalid record {}, missing value'
                            .format(self.fqdn))

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


class CnameRecord(_ValueMixin, Record):
    _type = 'CNAME'

    def _process_value(self, value):
        if not value.endswith('.'):
            raise Exception('Invalid record {}, value {} missing trailing .'
                            .format(self.fqdn, value))
        return value.lower()


class MxValue(object):

    def __init__(self, value):
        # TODO: rename preference
        self.priority = int(value['priority'])
        # TODO: rename to exchange?
        self.value = value['value'].lower()

    @property
    def data(self):
        return {
            'priority': self.priority,
            'value': self.value,
        }

    def __cmp__(self, other):
        if self.priority == other.priority:
            return cmp(self.value, other.value)
        return cmp(self.priority, other.priority)

    def __repr__(self):
        return "'{} {}'".format(self.priority, self.value)


class MxRecord(_ValuesMixin, Record):
    _type = 'MX'

    def _process_values(self, values):
        ret = []
        for value in values:
            try:
                ret.append(MxValue(value))
            except KeyError as e:
                raise Exception('Invalid value in record {}, missing {}'
                                .format(self.fqdn, e.args[0]))
        return ret


class NaptrValue(object):

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

    def _process_values(self, values):
        ret = []
        for value in values:
            try:
                ret.append(NaptrValue(value))
            except KeyError as e:
                raise Exception('Invalid value in record {}, missing {}'
                                .format(self.fqdn, e.args[0]))
        return ret


class NsRecord(_ValuesMixin, Record):
    _type = 'NS'

    def _process_values(self, values):
        ret = []
        for ns in values:
            if not ns.endswith('.'):
                raise Exception('Invalid record {}, value {} missing '
                                'trailing .'.format(self.fqdn, ns))
            ret.append(ns.lower())
        return ret


class PtrRecord(_ValueMixin, Record):
    _type = 'PTR'

    def _process_value(self, value):
        if not value.endswith('.'):
            raise Exception('Invalid record {}, value {} missing trailing .'
                            .format(self.fqdn, value))
        return value.lower()


class SshfpValue(object):

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

    def _process_values(self, values):
        ret = []
        for value in values:
            try:
                ret.append(SshfpValue(value))
            except KeyError as e:
                raise Exception('Invalid value in record {}, missing {}'
                                .format(self.fqdn, e.args[0]))
        return ret


class SpfRecord(_ValuesMixin, Record):
    _type = 'SPF'

    def _process_values(self, values):
        return values


class SrvValue(object):

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

    def __init__(self, zone, name, data, source=None):
        if not self._name_re.match(name):
            raise Exception('Invalid name {}.{}'.format(name, zone.name))
        super(SrvRecord, self).__init__(zone, name, data, source)

    def _process_values(self, values):
        ret = []
        for value in values:
            try:
                ret.append(SrvValue(value))
            except KeyError as e:
                raise Exception('Invalid value in record {}, missing {}'
                                .format(self.fqdn, e.args[0]))
        return ret


class TxtRecord(_ValuesMixin, Record):
    _type = 'TXT'

    def _process_values(self, values):
        for value in values:
            if _unescaped_semicolon_re.search(value):
                raise Exception('Invalid record {}, unescaped ;'
                                .format(self.fqdn))
        return values
