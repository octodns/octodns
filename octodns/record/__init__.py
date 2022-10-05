#
#
#

from collections import defaultdict
from ipaddress import IPv4Address as _IPv4Address, IPv6Address as _IPv6Address
from logging import getLogger
import re

from fqdn import FQDN

from ..equality import EqualityTupleMixin
from ..idna import IdnaError, idna_decode, idna_encode
from .geo import GeoCodes


class Change(EqualityTupleMixin):
    def __init__(self, existing, new):
        self.existing = existing
        self.new = new

    @property
    def record(self):
        'Returns new if we have one, existing otherwise'
        return self.new or self.existing

    def _equality_tuple(self):
        return (self.CLASS_ORDERING, self.record.name, self.record._type)


class Create(Change):
    CLASS_ORDERING = 1

    def __init__(self, new):
        super().__init__(None, new)

    def __repr__(self, leader=''):
        source = self.new.source.id if self.new.source else ''
        return f'Create {self.new} ({source})'


class Update(Change):
    CLASS_ORDERING = 2

    # Leader is just to allow us to work around heven eating leading whitespace
    # in our output. When we call this from the Manager.sync plan summary
    # section we'll pass in a leader, otherwise we'll just let it default and
    # do nothing
    def __repr__(self, leader=''):
        source = self.new.source.id if self.new.source else ''
        return (
            f'Update\n{leader}    {self.existing} ->\n'
            f'{leader}    {self.new} ({source})'
        )


class Delete(Change):
    CLASS_ORDERING = 0

    def __init__(self, existing):
        super().__init__(existing, None)

    def __repr__(self, leader=''):
        return f'Delete {self.existing}'


class RecordException(Exception):
    pass


class RrParseError(RecordException):
    def __init__(self, message='failed to parse string value as RR text'):
        super().__init__(message)


class ValidationError(RecordException):
    @classmethod
    def build_message(cls, fqdn, reasons):
        reasons = '\n  - '.join(reasons)
        return f'Invalid record {idna_decode(fqdn)}\n  - {reasons}'

    def __init__(self, fqdn, reasons):
        super().__init__(self.build_message(fqdn, reasons))
        self.fqdn = fqdn
        self.reasons = reasons


class Rr(object):
    '''
    Simple object intended to be used with Record.from_rrs to allow providers
    that work with RFC formatted rdata to share centralized parsing/encoding
    code
    '''

    def __init__(self, name, _type, ttl, rdata):
        self.name = name
        self._type = _type
        self.ttl = ttl
        self.rdata = rdata

    def __repr__(self):
        return f'Rr<{self.name}, {self._type}, {self.ttl}, {self.rdata}'


class Record(EqualityTupleMixin):
    log = getLogger('Record')

    _CLASSES = {}

    @classmethod
    def register_type(cls, _class, _type=None):
        if _type is None:
            _type = _class._type
        existing = cls._CLASSES.get(_type)
        if existing:
            module = existing.__module__
            name = existing.__name__
            msg = f'Type "{_type}" already registered by {module}.{name}'
            raise RecordException(msg)
        cls._CLASSES[_type] = _class

    @classmethod
    def registered_types(cls):
        return cls._CLASSES

    @classmethod
    def new(cls, zone, name, data, source=None, lenient=False):
        reasons = []
        try:
            name = idna_encode(str(name))
        except IdnaError as e:
            # convert the error into a reason
            reasons.append(str(e))
            name = str(name)
        fqdn = f'{name}.{zone.name}' if name else zone.name
        try:
            _type = data['type']
        except KeyError:
            raise Exception(f'Invalid record {idna_decode(fqdn)}, missing type')
        try:
            _class = cls._CLASSES[_type]
        except KeyError:
            raise Exception(f'Unknown record type: "{_type}"')
        reasons.extend(_class.validate(name, fqdn, data))
        try:
            lenient |= data['octodns']['lenient']
        except KeyError:
            pass
        if reasons:
            if lenient:
                cls.log.warning(ValidationError.build_message(fqdn, reasons))
            else:
                raise ValidationError(fqdn, reasons)
        return _class(zone, name, data, source=source)

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = []
        if name == '@':
            reasons.append('invalid name "@", use "" instead')
        n = len(fqdn)
        if n > 253:
            reasons.append(
                f'invalid fqdn, "{idna_decode(fqdn)}" is too long at {n} '
                'chars, max is 253'
            )
        for label in name.split('.'):
            n = len(label)
            if n > 63:
                reasons.append(
                    f'invalid label, "{label}" is too long at {n}'
                    ' chars, max is 63'
                )
        # TODO: look at the idna lib for a lot more potential validations...
        try:
            ttl = int(data['ttl'])
            if ttl < 0:
                reasons.append('invalid ttl')
        except KeyError:
            reasons.append('missing ttl')
        try:
            if data['octodns']['healthcheck']['protocol'] not in (
                'HTTP',
                'HTTPS',
                'TCP',
            ):
                reasons.append('invalid healthcheck protocol')
        except KeyError:
            pass
        return reasons

    @classmethod
    def from_rrs(cls, zone, rrs, lenient=False):
        # group records by name & type so that multiple rdatas can be combined
        # into a single record when needed
        grouped = defaultdict(list)
        for rr in rrs:
            grouped[(rr.name, rr._type)].append(rr)

        records = []
        # walk the grouped rrs converting each one to data and then create a
        # record with that data
        for _, rrs in sorted(grouped.items()):
            rr = rrs[0]
            name = zone.hostname_from_fqdn(rr.name)
            _class = cls._CLASSES[rr._type]
            data = _class.data_from_rrs(rrs)
            record = Record.new(zone, name, data, lenient=lenient)
            records.append(record)

        return records

    def __init__(self, zone, name, data, source=None):
        self.zone = zone
        if name:
            # internally everything is idna
            self.name = idna_encode(str(name))
            # we'll keep a decoded version around for logs and errors
            self.decoded_name = idna_decode(self.name)
        else:
            self.name = self.decoded_name = name
        self.log.debug(
            '__init__: zone.name=%s, type=%11s, name=%s',
            zone.decoded_name,
            self.__class__.__name__,
            self.decoded_name,
        )
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
        # TODO: these should be calculated and set in __init__ rather than on
        # each use
        if self.name:
            return f'{self.name}.{self.zone.name}'
        return self.zone.name

    @property
    def decoded_fqdn(self):
        if self.decoded_name:
            return f'{self.decoded_name}.{self.zone.decoded_name}'
        return self.zone.decoded_name

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
        data['octodns'] = self._octodns

        return Record.new(
            zone if zone else self.zone,
            self.name,
            data,
            self.source,
            lenient=True,
        )

    # NOTE: we're using __hash__ and ordering methods that consider Records
    # equivalent if they have the same name & _type. Values are ignored. This
    # is useful when computing diffs/changes.

    def __hash__(self):
        return f'{self.name}:{self._type}'.__hash__()

    def _equality_tuple(self):
        return (self.name, self._type)

    def __repr__(self):
        # Make sure this is always overridden
        raise NotImplementedError('Abstract base class, __repr__ required')


class GeoValue(EqualityTupleMixin):
    geo_re = re.compile(
        r'^(?P<continent_code>\w\w)(-(?P<country_code>\w\w)'
        r'(-(?P<subdivision_code>\w\w))?)?$'
    )

    @classmethod
    def _validate_geo(cls, code):
        reasons = []
        match = cls.geo_re.match(code)
        if not match:
            reasons.append(f'invalid geo "{code}"')
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
        return (
            self.continent_code,
            self.country_code,
            self.subdivision_code,
            self.values,
        )

    def __repr__(self):
        return (
            f"'Geo {self.continent_code} {self.country_code} "
            "{self.subdivision_code} {self.values}'"
        )


class ValuesMixin(object):
    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = super().validate(name, fqdn, data)

        values = data.get('values', data.get('value', []))

        reasons.extend(cls._value_type.validate(values, cls._type))

        return reasons

    @classmethod
    def data_from_rrs(cls, rrs):
        # type and TTL come from the first rr
        rr = rrs[0]
        # values come from parsing the rdata portion of all rrs
        values = [cls._value_type.parse_rdata_text(rr.rdata) for rr in rrs]
        return {'ttl': rr.ttl, 'type': rr._type, 'values': values}

    def __init__(self, zone, name, data, source=None):
        super().__init__(zone, name, data, source=source)
        try:
            values = data['values']
        except KeyError:
            values = [data['value']]
        self.values = sorted(self._value_type.process(values))

    def changes(self, other, target):
        if self.values != other.values:
            return Update(self, other)
        return super().changes(other, target)

    def _data(self):
        ret = super()._data()
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

    @property
    def rrs(self):
        return (
            self.fqdn,
            self.ttl,
            self._type,
            [v.rdata_text for v in self.values],
        )

    def __repr__(self):
        values = "', '".join([str(v) for v in self.values])
        klass = self.__class__.__name__
        return f"<{klass} {self._type} {self.ttl}, {self.decoded_fqdn}, ['{values}']>"


class _GeoMixin(ValuesMixin):
    '''
    Adds GeoDNS support to a record.

    Must be included before `Record`.
    '''

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = super().validate(name, fqdn, data)
        try:
            geo = dict(data['geo'])
            for code, values in geo.items():
                reasons.extend(GeoValue._validate_geo(code))
                reasons.extend(cls._value_type.validate(values, cls._type))
        except KeyError:
            pass
        return reasons

    def __init__(self, zone, name, data, *args, **kwargs):
        super().__init__(zone, name, data, *args, **kwargs)
        try:
            self.geo = dict(data['geo'])
        except KeyError:
            self.geo = {}
        for code, values in self.geo.items():
            self.geo[code] = GeoValue(code, values)

    def _data(self):
        ret = super()._data()
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
        return super().changes(other, target)

    def __repr__(self):
        if self.geo:
            klass = self.__class__.__name__
            return (
                f'<{klass} {self._type} {self.ttl}, {self.decoded_fqdn}, '
                f'{self.values}, {self.geo}>'
            )
        return super().__repr__()


class ValueMixin(object):
    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = super().validate(name, fqdn, data)
        reasons.extend(
            cls._value_type.validate(data.get('value', None), cls._type)
        )
        return reasons

    @classmethod
    def data_from_rrs(cls, rrs):
        # single value, so single rr only...
        rr = rrs[0]
        return {
            'ttl': rr.ttl,
            'type': rr._type,
            'value': cls._value_type.parse_rdata_text(rr.rdata),
        }

    def __init__(self, zone, name, data, source=None):
        super().__init__(zone, name, data, source=source)
        self.value = self._value_type.process(data['value'])

    def changes(self, other, target):
        if self.value != other.value:
            return Update(self, other)
        return super().changes(other, target)

    def _data(self):
        ret = super()._data()
        if self.value:
            ret['value'] = getattr(self.value, 'data', self.value)
        return ret

    @property
    def rrs(self):
        return self.fqdn, self.ttl, self._type, [self.value.rdata_text]

    def __repr__(self):
        klass = self.__class__.__name__
        return f'<{klass} {self._type} {self.ttl}, {self.decoded_fqdn}, {self.value}>'


class _DynamicPool(object):
    log = getLogger('_DynamicPool')

    def __init__(self, _id, data, value_type):
        self._id = _id

        values = [
            {
                'value': value_type(d['value']),
                'weight': d.get('weight', 1),
                'status': d.get('status', 'obey'),
            }
            for d in data['values']
        ]
        values.sort(key=lambda d: d['value'])

        # normalize weight of a single-value pool
        if len(values) == 1:
            weight = data['values'][0].get('weight', 1)
            if weight != 1:
                self.log.warning(
                    'Using weight=1 instead of %s for single-value pool %s',
                    weight,
                    _id,
                )
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
        return f'{self.data}'


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
        return f'{self.data}'


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
        return {'pools': pools, 'rules': rules}

    def __eq__(self, other):
        if not isinstance(other, _Dynamic):
            return False
        ret = self.pools == other.pools and self.rules == other.rules
        return ret

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return f'{self.pools}, {self.rules}'


class _DynamicMixin(object):
    geo_re = re.compile(
        r'^(?P<continent_code>\w\w)(-(?P<country_code>\w\w)'
        r'(-(?P<subdivision_code>\w\w))?)?$'
    )

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = super().validate(name, fqdn, data)

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
                    reasons.append(f'pool "{_id}" must be a dict')
                    continue
                try:
                    values = pool['values']
                except KeyError:
                    reasons.append(f'pool "{_id}" is missing values')
                    continue

                pools_exist.add(_id)

                for i, value in enumerate(values):
                    value_num = i + 1
                    try:
                        weight = value['weight']
                        weight = int(weight)
                        if weight < 1 or weight > 100:
                            reasons.append(
                                f'invalid weight "{weight}" in '
                                f'pool "{_id}" value {value_num}'
                            )
                    except KeyError:
                        pass
                    except ValueError:
                        reasons.append(
                            f'invalid weight "{weight}" in '
                            f'pool "{_id}" value {value_num}'
                        )

                    try:
                        status = value['status']
                        if status not in ['up', 'down', 'obey']:
                            reasons.append(
                                f'invalid status "{status}" in '
                                f'pool "{_id}" value {value_num}'
                            )
                    except KeyError:
                        pass

                    try:
                        value = value['value']
                        reasons.extend(
                            cls._value_type.validate(value, cls._type)
                        )
                    except KeyError:
                        reasons.append(
                            f'missing value in pool "{_id}" '
                            f'value {value_num}'
                        )

                if len(values) == 1 and values[0].get('weight', 1) != 1:
                    reasons.append(
                        f'pool "{_id}" has single value with weight!=1'
                    )

                fallback = pool.get('fallback', None)
                if fallback is not None:
                    if fallback in pools:
                        pools_seen_as_fallback.add(fallback)
                    else:
                        reasons.append(
                            f'undefined fallback "{fallback}" '
                            f'for pool "{_id}"'
                        )

                # Check for loops
                fallback = pools[_id].get('fallback', None)
                seen = [_id, fallback]
                while fallback is not None:
                    # See if there's a next fallback
                    fallback = pools.get(fallback, {}).get('fallback', None)
                    if fallback in seen:
                        loop = ' -> '.join(seen)
                        reasons.append(f'loop in pool fallbacks: {loop}')
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
                    reasons.append(f'rule {rule_num} missing pool')
                    continue

                try:
                    geos = rule['geos']
                except KeyError:
                    geos = []

                if not isinstance(pool, str):
                    reasons.append(f'rule {rule_num} invalid pool "{pool}"')
                else:
                    if pool not in pools:
                        reasons.append(
                            f'rule {rule_num} undefined pool ' f'"{pool}"'
                        )
                    elif pool in pools_seen and geos:
                        reasons.append(
                            f'rule {rule_num} invalid, target '
                            f'pool "{pool}" reused'
                        )
                    pools_seen.add(pool)

                if not geos:
                    if seen_default:
                        reasons.append(f'rule {rule_num} duplicate default')
                    seen_default = True

                if not isinstance(geos, (list, tuple)):
                    reasons.append(f'rule {rule_num} geos must be a list')
                else:
                    for geo in geos:
                        reasons.extend(
                            GeoCodes.validate(geo, f'rule {rule_num} ')
                        )

        unused = pools_exist - pools_seen - pools_seen_as_fallback
        if unused:
            unused = '", "'.join(sorted(unused))
            reasons.append(f'unused pools: "{unused}"')

        return reasons

    def __init__(self, zone, name, data, *args, **kwargs):
        super().__init__(zone, name, data, *args, **kwargs)

        self.dynamic = {}

        if 'dynamic' not in data:
            return

        # pools
        try:
            pools = dict(data['dynamic']['pools'])
        except:
            pools = {}

        for _id, pool in sorted(pools.items()):
            pools[_id] = _DynamicPool(_id, pool, self._value_type)

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
        ret = super()._data()
        if self.dynamic:
            ret['dynamic'] = self.dynamic._data()
        return ret

    def changes(self, other, target):
        if target.SUPPORTS_DYNAMIC:
            if self.dynamic != other.dynamic:
                return Update(self, other)
        return super().changes(other, target)

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

            klass = self.__class__.__name__
            return (
                f'<{klass} {self._type} {self.ttl}, {self.decoded_fqdn}, '
                f'{values}, {self.dynamic}>'
            )
        return super().__repr__()


class _TargetValue(str):
    @classmethod
    def parse_rdata_text(self, value):
        return value

    @classmethod
    def validate(cls, data, _type):
        reasons = []
        if data == '':
            reasons.append('empty value')
        elif not data:
            reasons.append('missing value')
        else:
            data = idna_encode(data)
            if not FQDN(str(data), allow_underscores=True).is_valid:
                reasons.append(f'{_type} value "{data}" is not a valid FQDN')
            elif not data.endswith('.'):
                reasons.append(f'{_type} value "{data}" missing trailing .')
        return reasons

    @classmethod
    def process(cls, value):
        if value:
            return cls(value)
        return None

    def __new__(cls, v):
        v = idna_encode(v)
        return super().__new__(cls, v)

    @property
    def rdata_text(self):
        return self


class CnameValue(_TargetValue):
    pass


class DnameValue(_TargetValue):
    pass


class _IpAddress(str):
    @classmethod
    def parse_rdata_text(cls, value):
        return value

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
                    cls._address_type(str(value))
                except Exception:
                    addr_name = cls._address_name
                    reasons.append(f'invalid {addr_name} address "{value}"')
        return reasons

    @classmethod
    def process(cls, values):
        # Translating None into '' so that the list will be sortable in
        # python3, get everything to str first
        values = [v if v is not None else '' for v in values]
        # Now round trip all non-'' through the address type and back to a str
        # to normalize the address representation.
        return [cls(v) if v != '' else '' for v in values]

    def __new__(cls, v):
        v = str(cls._address_type(v))
        return super().__new__(cls, v)

    @property
    def rdata_text(self):
        return self


class Ipv4Address(_IpAddress):
    _address_type = _IPv4Address
    _address_name = 'IPv4'


class ARecord(_DynamicMixin, _GeoMixin, Record):
    _type = 'A'
    _value_type = Ipv4Address


Record.register_type(ARecord)


class Ipv6Address(_IpAddress):
    _address_type = _IPv6Address
    _address_name = 'IPv6'


class AaaaRecord(_DynamicMixin, _GeoMixin, Record):
    _type = 'AAAA'
    _value_type = Ipv6Address


Record.register_type(AaaaRecord)


class AliasValue(_TargetValue):
    pass


class AliasRecord(ValueMixin, Record):
    _type = 'ALIAS'
    _value_type = AliasValue

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = []
        if name != '':
            reasons.append('non-root ALIAS not allowed')
        reasons.extend(super().validate(name, fqdn, data))
        return reasons


Record.register_type(AliasRecord)


class CaaValue(EqualityTupleMixin, dict):
    # https://tools.ietf.org/html/rfc6844#page-5

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            flags, tag, value = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            flags = int(flags)
        except ValueError:
            pass
        return {'flags': flags, 'tag': tag, 'value': value}

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            try:
                flags = int(value.get('flags', 0))
                if flags < 0 or flags > 255:
                    reasons.append(f'invalid flags "{flags}"')
            except ValueError:
                reasons.append(f'invalid flags "{value["flags"]}"')

            if 'tag' not in value:
                reasons.append('missing tag')
            if 'value' not in value:
                reasons.append('missing value')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'flags': int(value.get('flags', 0)),
                'tag': value['tag'],
                'value': value['value'],
            }
        )

    @property
    def flags(self):
        return self['flags']

    @flags.setter
    def flags(self, value):
        self['flags'] = value

    @property
    def tag(self):
        return self['tag']

    @tag.setter
    def tag(self, value):
        self['tag'] = value

    @property
    def value(self):
        return self['value']

    @value.setter
    def value(self, value):
        self['value'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return f'{self.flags} {self.tag} {self.value}'

    def _equality_tuple(self):
        return (self.flags, self.tag, self.value)

    def __repr__(self):
        return f'{self.flags} {self.tag} "{self.value}"'


class CaaRecord(ValuesMixin, Record):
    _type = 'CAA'
    _value_type = CaaValue


Record.register_type(CaaRecord)


class CnameRecord(_DynamicMixin, ValueMixin, Record):
    _type = 'CNAME'
    _value_type = CnameValue

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = []
        if name == '':
            reasons.append('root CNAME not allowed')
        reasons.extend(super().validate(name, fqdn, data))
        return reasons


Record.register_type(CnameRecord)


class DnameRecord(_DynamicMixin, ValueMixin, Record):
    _type = 'DNAME'
    _value_type = DnameValue


Record.register_type(DnameRecord)


class LocValue(EqualityTupleMixin, dict):
    # TODO: this does not really match the RFC, but it's stuck using the details
    # of how the type was impelemented. Would be nice to rework things to match
    # while maintaining backwards compatibility.
    # https://www.rfc-editor.org/rfc/rfc1876.html

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            value = value.replace('m', '')
            (
                lat_degrees,
                lat_minutes,
                lat_seconds,
                lat_direction,
                long_degrees,
                long_minutes,
                long_seconds,
                long_direction,
                altitude,
                size,
                precision_horz,
                precision_vert,
            ) = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            lat_degrees = int(lat_degrees)
        except ValueError:
            pass
        try:
            lat_minutes = int(lat_minutes)
        except ValueError:
            pass
        try:
            long_degrees = int(long_degrees)
        except ValueError:
            pass
        try:
            long_minutes = int(long_minutes)
        except ValueError:
            pass
        try:
            lat_seconds = float(lat_seconds)
        except ValueError:
            pass
        try:
            long_seconds = float(long_seconds)
        except ValueError:
            pass
        try:
            altitude = float(altitude)
        except ValueError:
            pass
        try:
            size = float(size)
        except ValueError:
            pass
        try:
            precision_horz = float(precision_horz)
        except ValueError:
            pass
        try:
            precision_vert = float(precision_vert)
        except ValueError:
            pass
        return {
            'lat_degrees': lat_degrees,
            'lat_minutes': lat_minutes,
            'lat_seconds': lat_seconds,
            'lat_direction': lat_direction,
            'long_degrees': long_degrees,
            'long_minutes': long_minutes,
            'long_seconds': long_seconds,
            'long_direction': long_direction,
            'altitude': altitude,
            'size': size,
            'precision_horz': precision_horz,
            'precision_vert': precision_vert,
        }

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

        direction_keys = ['lat_direction', 'long_direction']

        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            for key in int_keys:
                try:
                    int(value[key])
                    if (
                        (
                            key == 'lat_degrees'
                            and not 0 <= int(value[key]) <= 90
                        )
                        or (
                            key == 'long_degrees'
                            and not 0 <= int(value[key]) <= 180
                        )
                        or (
                            key in ['lat_minutes', 'long_minutes']
                            and not 0 <= int(value[key]) <= 59
                        )
                    ):
                        reasons.append(
                            f'invalid value for {key} ' f'"{value[key]}"'
                        )
                except KeyError:
                    reasons.append(f'missing {key}')
                except ValueError:
                    reasons.append(f'invalid {key} "{value[key]}"')

            for key in float_keys:
                try:
                    float(value[key])
                    if (
                        (
                            key in ['lat_seconds', 'long_seconds']
                            and not 0 <= float(value[key]) <= 59.999
                        )
                        or (
                            key == 'altitude'
                            and not -100000.00
                            <= float(value[key])
                            <= 42849672.95
                        )
                        or (
                            key in ['size', 'precision_horz', 'precision_vert']
                            and not 0 <= float(value[key]) <= 90000000.00
                        )
                    ):
                        reasons.append(
                            f'invalid value for {key} ' f'"{value[key]}"'
                        )
                except KeyError:
                    reasons.append(f'missing {key}')
                except ValueError:
                    reasons.append(f'invalid {key} "{value[key]}"')

            for key in direction_keys:
                try:
                    str(value[key])
                    if key == 'lat_direction' and value[key] not in ['N', 'S']:
                        reasons.append(
                            f'invalid direction for {key} ' f'"{value[key]}"'
                        )
                    if key == 'long_direction' and value[key] not in ['E', 'W']:
                        reasons.append(
                            f'invalid direction for {key} ' f'"{value[key]}"'
                        )
                except KeyError:
                    reasons.append(f'missing {key}')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'lat_degrees': int(value['lat_degrees']),
                'lat_minutes': int(value['lat_minutes']),
                'lat_seconds': float(value['lat_seconds']),
                'lat_direction': value['lat_direction'].upper(),
                'long_degrees': int(value['long_degrees']),
                'long_minutes': int(value['long_minutes']),
                'long_seconds': float(value['long_seconds']),
                'long_direction': value['long_direction'].upper(),
                'altitude': float(value['altitude']),
                'size': float(value['size']),
                'precision_horz': float(value['precision_horz']),
                'precision_vert': float(value['precision_vert']),
            }
        )

    @property
    def lat_degrees(self):
        return self['lat_degrees']

    @lat_degrees.setter
    def lat_degrees(self, value):
        self['lat_degrees'] = value

    @property
    def lat_minutes(self):
        return self['lat_minutes']

    @lat_minutes.setter
    def lat_minutes(self, value):
        self['lat_minutes'] = value

    @property
    def lat_seconds(self):
        return self['lat_seconds']

    @lat_seconds.setter
    def lat_seconds(self, value):
        self['lat_seconds'] = value

    @property
    def lat_direction(self):
        return self['lat_direction']

    @lat_direction.setter
    def lat_direction(self, value):
        self['lat_direction'] = value

    @property
    def long_degrees(self):
        return self['long_degrees']

    @long_degrees.setter
    def long_degrees(self, value):
        self['long_degrees'] = value

    @property
    def long_minutes(self):
        return self['long_minutes']

    @long_minutes.setter
    def long_minutes(self, value):
        self['long_minutes'] = value

    @property
    def long_seconds(self):
        return self['long_seconds']

    @long_seconds.setter
    def long_seconds(self, value):
        self['long_seconds'] = value

    @property
    def long_direction(self):
        return self['long_direction']

    @long_direction.setter
    def long_direction(self, value):
        self['long_direction'] = value

    @property
    def altitude(self):
        return self['altitude']

    @altitude.setter
    def altitude(self, value):
        self['altitude'] = value

    @property
    def size(self):
        return self['size']

    @size.setter
    def size(self, value):
        self['size'] = value

    @property
    def precision_horz(self):
        return self['precision_horz']

    @precision_horz.setter
    def precision_horz(self, value):
        self['precision_horz'] = value

    @property
    def precision_vert(self):
        return self['precision_vert']

    @precision_vert.setter
    def precision_vert(self, value):
        self['precision_vert'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return f'{self.lat_degrees} {self.lat_minutes} {self.lat_seconds} {self.lat_direction} {self.long_degrees} {self.long_minutes} {self.long_seconds} {self.long_direction} {self.altitude}m {self.size}m {self.precision_horz}m {self.precision_vert}m'

    def __hash__(self):
        return hash(
            (
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
        )

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
        return (
            f"'{self.lat_degrees} {self.lat_minutes} "
            f"{self.lat_seconds:.3f} {self.lat_direction} "
            f"{self.long_degrees} {self.long_minutes} "
            f"{self.long_seconds:.3f} {self.long_direction} "
            f"{self.altitude:.2f}m {self.size:.2f}m "
            f"{self.precision_horz:.2f}m {self.precision_vert:.2f}m'"
        )


class LocRecord(ValuesMixin, Record):
    _type = 'LOC'
    _value_type = LocValue


Record.register_type(LocRecord)


class MxValue(EqualityTupleMixin, dict):
    @classmethod
    def parse_rdata_text(cls, value):
        try:
            preference, exchange = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            preference = int(preference)
        except ValueError:
            pass
        return {'preference': preference, 'exchange': exchange}

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
                reasons.append(f'invalid preference "{value["preference"]}"')
            exchange = None
            try:
                exchange = value.get('exchange', None) or value['value']
                if not exchange:
                    reasons.append('missing exchange')
                    continue
                exchange = idna_encode(exchange)
                if (
                    exchange != '.'
                    and not FQDN(exchange, allow_underscores=True).is_valid
                ):
                    reasons.append(
                        f'Invalid MX exchange "{exchange}" is not '
                        'a valid FQDN.'
                    )
                elif not exchange.endswith('.'):
                    reasons.append(f'MX value "{exchange}" missing trailing .')
            except KeyError:
                reasons.append('missing exchange')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        # RFC1035 says preference, half the providers use priority
        try:
            preference = value['preference']
        except KeyError:
            preference = value['priority']
        # UNTIL 1.0 remove value fallback
        try:
            exchange = value['exchange']
        except KeyError:
            exchange = value['value']
        super().__init__(
            {'preference': int(preference), 'exchange': idna_encode(exchange)}
        )

    @property
    def preference(self):
        return self['preference']

    @preference.setter
    def preference(self, value):
        self['preference'] = value

    @property
    def exchange(self):
        return self['exchange']

    @exchange.setter
    def exchange(self, value):
        self['exchange'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return f'{self.preference} {self.exchange}'

    def __hash__(self):
        return hash((self.preference, self.exchange))

    def _equality_tuple(self):
        return (self.preference, self.exchange)

    def __repr__(self):
        return f"'{self.preference} {self.exchange}'"


class MxRecord(ValuesMixin, Record):
    _type = 'MX'
    _value_type = MxValue


Record.register_type(MxRecord)


class NaptrValue(EqualityTupleMixin, dict):
    VALID_FLAGS = ('S', 'A', 'U', 'P')

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            (
                order,
                preference,
                flags,
                service,
                regexp,
                replacement,
            ) = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            order = int(order)
            preference = int(preference)
        except ValueError:
            pass
        return {
            'order': order,
            'preference': preference,
            'flags': flags,
            'service': service,
            'regexp': regexp,
            'replacement': replacement,
        }

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
                reasons.append(f'invalid order "{value["order"]}"')
            try:
                int(value['preference'])
            except KeyError:
                reasons.append('missing preference')
            except ValueError:
                reasons.append(f'invalid preference "{value["preference"]}"')
            try:
                flags = value['flags']
                if flags not in cls.VALID_FLAGS:
                    reasons.append(f'unrecognized flags "{flags}"')
            except KeyError:
                reasons.append('missing flags')

            # TODO: validate these... they're non-trivial
            for k in ('service', 'regexp', 'replacement'):
                if k not in value:
                    reasons.append(f'missing {k}')

        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'order': int(value['order']),
                'preference': int(value['preference']),
                'flags': value['flags'],
                'service': value['service'],
                'regexp': value['regexp'],
                'replacement': value['replacement'],
            }
        )

    @property
    def order(self):
        return self['order']

    @order.setter
    def order(self, value):
        self['order'] = value

    @property
    def preference(self):
        return self['preference']

    @preference.setter
    def preference(self, value):
        self['preference'] = value

    @property
    def flags(self):
        return self['flags']

    @flags.setter
    def flags(self, value):
        self['flags'] = value

    @property
    def service(self):
        return self['service']

    @service.setter
    def service(self, value):
        self['service'] = value

    @property
    def regexp(self):
        return self['regexp']

    @regexp.setter
    def regexp(self, value):
        self['regexp'] = value

    @property
    def replacement(self):
        return self['replacement']

    @replacement.setter
    def replacement(self, value):
        self['replacement'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return f'{self.order} {self.preference} {self.flags} {self.service} {self.regexp} {self.replacement}'

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (
            self.order,
            self.preference,
            self.flags,
            self.service,
            self.regexp,
            self.replacement,
        )

    def __repr__(self):
        flags = self.flags if self.flags is not None else ''
        service = self.service if self.service is not None else ''
        regexp = self.regexp if self.regexp is not None else ''
        return (
            f"'{self.order} {self.preference} \"{flags}\" \"{service}\" "
            f"\"{regexp}\" {self.replacement}'"
        )


class NaptrRecord(ValuesMixin, Record):
    _type = 'NAPTR'
    _value_type = NaptrValue


Record.register_type(NaptrRecord)


# much like _TargetValue, but geared towards multiple values
class _TargetsValue(str):
    @classmethod
    def parse_rdata_text(cls, value):
        return value

    @classmethod
    def validate(cls, data, _type):
        if not data:
            return ['missing value(s)']
        elif not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            value = idna_encode(value)
            if not FQDN(value, allow_underscores=True).is_valid:
                reasons.append(
                    f'Invalid {_type} value "{value}" is not a valid FQDN.'
                )
            elif not value.endswith('.'):
                reasons.append(f'{_type} value "{value}" missing trailing .')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __new__(cls, v):
        v = idna_encode(v)
        return super().__new__(cls, v)

    @property
    def rdata_text(self):
        return self


class _NsValue(_TargetsValue):
    pass


class NsRecord(ValuesMixin, Record):
    _type = 'NS'
    _value_type = _NsValue


Record.register_type(NsRecord)


class PtrValue(_TargetsValue):
    pass


class PtrRecord(ValuesMixin, Record):
    _type = 'PTR'
    _value_type = PtrValue

    # This is for backward compatibility with providers that don't support
    # multi-value PTR records.
    @property
    def value(self):
        return self.values[0]


Record.register_type(PtrRecord)


class SshfpValue(EqualityTupleMixin, dict):
    VALID_ALGORITHMS = (1, 2, 3, 4)
    VALID_FINGERPRINT_TYPES = (1, 2)

    @classmethod
    def parse_rdata_text(self, value):
        try:
            algorithm, fingerprint_type, fingerprint = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            algorithm = int(algorithm)
        except ValueError:
            pass
        try:
            fingerprint_type = int(fingerprint_type)
        except ValueError:
            pass
        return {
            'algorithm': algorithm,
            'fingerprint_type': fingerprint_type,
            'fingerprint': fingerprint,
        }

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            try:
                algorithm = int(value['algorithm'])
                if algorithm not in cls.VALID_ALGORITHMS:
                    reasons.append(f'unrecognized algorithm "{algorithm}"')
            except KeyError:
                reasons.append('missing algorithm')
            except ValueError:
                reasons.append(f'invalid algorithm "{value["algorithm"]}"')
            try:
                fingerprint_type = int(value['fingerprint_type'])
                if fingerprint_type not in cls.VALID_FINGERPRINT_TYPES:
                    reasons.append(
                        'unrecognized fingerprint_type ' f'"{fingerprint_type}"'
                    )
            except KeyError:
                reasons.append('missing fingerprint_type')
            except ValueError:
                reasons.append(
                    'invalid fingerprint_type ' f'"{value["fingerprint_type"]}"'
                )
            if 'fingerprint' not in value:
                reasons.append('missing fingerprint')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'algorithm': int(value['algorithm']),
                'fingerprint_type': int(value['fingerprint_type']),
                'fingerprint': value['fingerprint'],
            }
        )

    @property
    def algorithm(self):
        return self['algorithm']

    @algorithm.setter
    def algorithm(self, value):
        self['algorithm'] = value

    @property
    def fingerprint_type(self):
        return self['fingerprint_type']

    @fingerprint_type.setter
    def fingerprint_type(self, value):
        self['fingerprint_type'] = value

    @property
    def fingerprint(self):
        return self['fingerprint']

    @fingerprint.setter
    def fingerprint(self, value):
        self['fingerprint'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return f'{self.algorithm} {self.fingerprint_type} {self.fingerprint}'

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (self.algorithm, self.fingerprint_type, self.fingerprint)

    def __repr__(self):
        return f"'{self.algorithm} {self.fingerprint_type} {self.fingerprint}'"


class SshfpRecord(ValuesMixin, Record):
    _type = 'SSHFP'
    _value_type = SshfpValue


Record.register_type(SshfpRecord)


class _ChunkedValuesMixin(ValuesMixin):
    CHUNK_SIZE = 255
    _unescaped_semicolon_re = re.compile(r'\w;')

    def chunked_value(self, value):
        value = value.replace('"', '\\"')
        vs = [
            value[i : i + self.CHUNK_SIZE]
            for i in range(0, len(value), self.CHUNK_SIZE)
        ]
        vs = '" "'.join(vs)
        return f'"{vs}"'

    @property
    def chunked_values(self):
        values = []
        for v in self.values:
            values.append(self.chunked_value(v))
        return values


class _ChunkedValue(str):
    _unescaped_semicolon_re = re.compile(r'\w;')

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            return value.replace(';', '\\;')
        except AttributeError:
            return value

    @classmethod
    def validate(cls, data, _type):
        if not data:
            return ['missing value(s)']
        elif not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            if cls._unescaped_semicolon_re.search(value):
                reasons.append(f'unescaped ; in "{value}"')
        return reasons

    @classmethod
    def process(cls, values):
        ret = []
        for v in values:
            if v and v[0] == '"':
                v = v[1:-1]
            ret.append(cls(v.replace('" "', '')))
        return ret

    @property
    def rdata_text(self):
        return self


class SpfRecord(_ChunkedValuesMixin, Record):
    _type = 'SPF'
    _value_type = _ChunkedValue


Record.register_type(SpfRecord)


class SrvValue(EqualityTupleMixin, dict):
    @classmethod
    def parse_rdata_text(self, value):
        try:
            priority, weight, port, target = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            priority = int(priority)
        except ValueError:
            pass
        try:
            weight = int(weight)
        except ValueError:
            pass
        try:
            port = int(port)
        except ValueError:
            pass
        return {
            'priority': priority,
            'weight': weight,
            'port': port,
            'target': target,
        }

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
                reasons.append(f'invalid priority "{value["priority"]}"')
            try:
                int(value['weight'])
            except KeyError:
                reasons.append('missing weight')
            except ValueError:
                reasons.append(f'invalid weight "{value["weight"]}"')
            try:
                int(value['port'])
            except KeyError:
                reasons.append('missing port')
            except ValueError:
                reasons.append(f'invalid port "{value["port"]}"')
            try:
                target = value['target']
                if not target:
                    reasons.append('missing target')
                    continue
                target = idna_encode(target)
                if not target.endswith('.'):
                    reasons.append(f'SRV value "{target}" missing trailing .')
                if (
                    target != '.'
                    and not FQDN(target, allow_underscores=True).is_valid
                ):
                    reasons.append(
                        f'Invalid SRV target "{target}" is not a valid FQDN.'
                    )
            except KeyError:
                reasons.append('missing target')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'priority': int(value['priority']),
                'weight': int(value['weight']),
                'port': int(value['port']),
                'target': idna_encode(value['target']),
            }
        )

    @property
    def priority(self):
        return self['priority']

    @priority.setter
    def priority(self, value):
        self['priority'] = value

    @property
    def weight(self):
        return self['weight']

    @weight.setter
    def weight(self, value):
        self['weight'] = value

    @property
    def port(self):
        return self['port']

    @port.setter
    def port(self, value):
        self['port'] = value

    @property
    def target(self):
        return self['target']

    @target.setter
    def target(self, value):
        self['target'] = value

    @property
    def data(self):
        return self

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (self.priority, self.weight, self.port, self.target)

    def __repr__(self):
        return f"'{self.priority} {self.weight} {self.port} {self.target}'"


class SrvRecord(ValuesMixin, Record):
    _type = 'SRV'
    _value_type = SrvValue
    _name_re = re.compile(r'^(\*|_[^\.]+)\.[^\.]+')

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = []
        if not cls._name_re.match(name):
            reasons.append('invalid name for SRV record')
        reasons.extend(super().validate(name, fqdn, data))
        return reasons


Record.register_type(SrvRecord)


class TlsaValue(EqualityTupleMixin, dict):
    @classmethod
    def parse_rdata_text(self, value):
        try:
            (
                certificate_usage,
                selector,
                matching_type,
                certificate_association_data,
            ) = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            certificate_usage = int(certificate_usage)
        except ValueError:
            pass
        try:
            selector = int(selector)
        except ValueError:
            pass
        try:
            matching_type = int(matching_type)
        except ValueError:
            pass
        return {
            'certificate_usage': certificate_usage,
            'selector': selector,
            'matching_type': matching_type,
            'certificate_association_data': certificate_association_data,
        }

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            try:
                certificate_usage = int(value.get('certificate_usage', 0))
                if certificate_usage < 0 or certificate_usage > 3:
                    reasons.append(
                        f'invalid certificate_usage ' f'"{certificate_usage}"'
                    )
            except ValueError:
                reasons.append(
                    f'invalid certificate_usage '
                    f'"{value["certificate_usage"]}"'
                )

            try:
                selector = int(value.get('selector', 0))
                if selector < 0 or selector > 1:
                    reasons.append(f'invalid selector "{selector}"')
            except ValueError:
                reasons.append(f'invalid selector "{value["selector"]}"')

            try:
                matching_type = int(value.get('matching_type', 0))
                if matching_type < 0 or matching_type > 2:
                    reasons.append(f'invalid matching_type "{matching_type}"')
            except ValueError:
                reasons.append(
                    f'invalid matching_type ' f'"{value["matching_type"]}"'
                )

            if 'certificate_usage' not in value:
                reasons.append('missing certificate_usage')
            if 'selector' not in value:
                reasons.append('missing selector')
            if 'matching_type' not in value:
                reasons.append('missing matching_type')
            if 'certificate_association_data' not in value:
                reasons.append('missing certificate_association_data')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'certificate_usage': int(value.get('certificate_usage', 0)),
                'selector': int(value.get('selector', 0)),
                'matching_type': int(value.get('matching_type', 0)),
                'certificate_association_data': value[
                    'certificate_association_data'
                ],
            }
        )

    @property
    def certificate_usage(self):
        return self['certificate_usage']

    @certificate_usage.setter
    def certificate_usage(self, value):
        self['certificate_usage'] = value

    @property
    def selector(self):
        return self['selector']

    @selector.setter
    def selector(self, value):
        self['selector'] = value

    @property
    def matching_type(self):
        return self['matching_type']

    @matching_type.setter
    def matching_type(self, value):
        self['matching_type'] = value

    @property
    def certificate_association_data(self):
        return self['certificate_association_data']

    @certificate_association_data.setter
    def certificate_association_data(self, value):
        self['certificate_association_data'] = value

    @property
    def rdata_text(self):
        return f'{self.certificate_usage} {self.selector} {self.matching_type} {self.certificate_association_data}'

    def _equality_tuple(self):
        return (
            self.certificate_usage,
            self.selector,
            self.matching_type,
            self.certificate_association_data,
        )

    def __repr__(self):
        return (
            f"'{self.certificate_usage} {self.selector} '"
            f"'{self.matching_type} {self.certificate_association_data}'"
        )


class TlsaRecord(ValuesMixin, Record):
    _type = 'TLSA'
    _value_type = TlsaValue


Record.register_type(TlsaRecord)


class _TxtValue(_ChunkedValue):
    pass


class TxtRecord(_ChunkedValuesMixin, Record):
    _type = 'TXT'
    _value_type = _TxtValue


Record.register_type(TxtRecord)


class UrlfwdValue(EqualityTupleMixin, dict):
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
                    reasons.append(f'unrecognized return code "{code}"')
            except KeyError:
                reasons.append('missing code')
            except ValueError:
                reasons.append(f'invalid return code "{value["code"]}"')
            try:
                masking = int(value['masking'])
                if masking not in cls.VALID_MASKS:
                    reasons.append(f'unrecognized masking setting "{masking}"')
            except KeyError:
                reasons.append('missing masking')
            except ValueError:
                reasons.append(f'invalid masking setting "{value["masking"]}"')
            try:
                query = int(value['query'])
                if query not in cls.VALID_QUERY:
                    reasons.append(f'unrecognized query setting "{query}"')
            except KeyError:
                reasons.append('missing query')
            except ValueError:
                reasons.append(f'invalid query setting "{value["query"]}"')
            for k in ('path', 'target'):
                if k not in value:
                    reasons.append(f'missing {k}')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'path': value['path'],
                'target': value['target'],
                'code': int(value['code']),
                'masking': int(value['masking']),
                'query': int(value['query']),
            }
        )

    @property
    def path(self):
        return self['path']

    @path.setter
    def path(self, value):
        self['path'] = value

    @property
    def target(self):
        return self['target']

    @target.setter
    def target(self, value):
        self['target'] = value

    @property
    def code(self):
        return self['code']

    @code.setter
    def code(self, value):
        self['code'] = value

    @property
    def masking(self):
        return self['masking']

    @masking.setter
    def masking(self, value):
        self['masking'] = value

    @property
    def query(self):
        return self['query']

    @query.setter
    def query(self, value):
        self['query'] = value

    def _equality_tuple(self):
        return (self.path, self.target, self.code, self.masking, self.query)

    def __hash__(self):
        return hash(
            (self.path, self.target, self.code, self.masking, self.query)
        )

    def __repr__(self):
        return f'"{self.path}" "{self.target}" {self.code} {self.masking} {self.query}'


class UrlfwdRecord(ValuesMixin, Record):
    _type = 'URLFWD'
    _value_type = UrlfwdValue


Record.register_type(UrlfwdRecord)
