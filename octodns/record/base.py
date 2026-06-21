#
#
#

from collections import defaultdict
from copy import deepcopy
from logging import getLogger

from ..context import ContextDict
from ..deprecation import deprecated
from ..equality import EqualityTupleMixin
from ..idna import IdnaError, idna_decode, idna_encode
from .change import Update
from .exception import RecordException, ValidationError
from .validator import RecordValidator, ValidatorRegistry


def unquote(s):
    if s and s[0] in ('"', "'"):
        return s[1:-1]
    return s


class NameValidator(RecordValidator):
    '''
    Validates record name and FQDN shape: rejects the legacy ``@`` alias,
    enforces the 253-char total FQDN length and 63-char per-label length
    limits from RFC 1035, and flags empty/double-dot labels.
    '''

    def validate(self, record_cls, name, fqdn, data):
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
        # in the case of endswith there's an implicit second . from the Zone
        if '..' in name or name.endswith('.'):
            reasons.append(f'invalid name, double `.` in "{idna_decode(fqdn)}"')
        # TODO: look at the idna lib for a lot more potential validations...
        return reasons


class TtlValidator(RecordValidator):
    '''
    Validates that the record has a ttl and that it is a non-negative
    integer.
    '''

    def validate(self, record_cls, name, fqdn, data):
        reasons = []
        try:
            ttl = int(data['ttl'])
            if ttl < 0:
                reasons.append('invalid ttl')
        except KeyError:
            reasons.append('missing ttl')
        return reasons


class HealthcheckValidator(RecordValidator):
    '''
    Validates the optional ``octodns.healthcheck.protocol`` setting, if
    present, is one of the supported protocols.
    '''

    def validate(self, record_cls, name, fqdn, data):
        reasons = []
        try:
            if data['octodns']['healthcheck']['protocol'] not in (
                'HTTP',
                'HTTPS',
                'ICMP',
                'TCP',
                'UDP',
            ):
                reasons.append('invalid healthcheck protocol')
        except KeyError:
            pass
        return reasons


class ValueTypeValidator(RecordValidator):
    '''
    Single-value variant of ``ValuesTypeValidator`` for records that use
    ``ValueMixin``: passes ``data['value']`` (or ``None``) through to the
    value type's validators.
    '''

    def __init__(self):
        super().__init__(id='_value-type')

    def validate(self, record_cls, name, fqdn, data):
        return _process_value_validators(
            record_cls._value_type, data.get('value', None), record_cls._type
        )


class ValuesTypeValidator(RecordValidator):
    '''
    Bridges a record's ``_value_type`` into the record-level validation
    pipeline: pulls ``values``/``value`` from ``data``, coerces to a list,
    and delegates to ``ValidatorRegistry.process_values``, which handles both
    the legacy ``validate`` classmethod on the value class (for 3rd-party
    back-compat) and any active ``ValueValidator`` instances for the type.
    '''

    def __init__(self):
        super().__init__(id='_values-type')

    def validate(self, record_cls, name, fqdn, data):
        values = data.get('values', data.get('value', []))
        values = (
            values
            if isinstance(values, (list, tuple))
            else ([] if values is None else [values])
        )
        return _process_value_validators(
            record_cls._value_type, values, record_cls._type
        )


class Record(EqualityTupleMixin):
    log = getLogger('Record')

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if 'validate' in cls.__dict__:
            deprecated(
                f'`{cls.__name__}.validate` override is DEPRECATED. '
                'Add a RecordValidator to `VALIDATORS` instead. '
                'Will be removed in 2.0',
                stacklevel=3,
            )

    REFERENCES = (
        'https://datatracker.ietf.org/doc/html/rfc1035',
        'https://datatracker.ietf.org/doc/html/rfc1123',
        'https://datatracker.ietf.org/doc/html/rfc2181',
        'https://datatracker.ietf.org/doc/html/rfc4592',
        'https://datatracker.ietf.org/doc/html/rfc5890',
    )

    _CLASSES = {}
    validators = ValidatorRegistry()

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
        # Walk the MRO to find VALIDATORS at any level
        for klass in _class.__mro__:
            for validator in klass.__dict__.get('VALIDATORS', ()):
                cls.register_validator(validator, types=[_type])
        # include value validators; rely on normal Python attribute
        # resolution so a value subclass can override its parent's
        # VALIDATORS rather than registering both
        vt = getattr(_class, '_value_type', None)
        for validator in getattr(vt, 'VALIDATORS', ()):
            cls.register_validator(validator, types=[_type])

    @classmethod
    def registered_types(cls):
        return cls._CLASSES

    @classmethod
    def register_validator(cls, validator, types=None):
        cls.validators.register(validator, types=types)

    @classmethod
    def enable_validators(cls, sets):
        cls.validators.enable_sets(sets)

    @classmethod
    def enable_validator(cls, id, types=None):
        cls.validators.enable(id, types=types)

    @classmethod
    def disable_validator(cls, validator_id, types=None):
        return cls.validators.disable(validator_id, types=types)

    @classmethod
    def registered_validators(cls):
        return cls.validators.registered()

    @classmethod
    def available_validators(cls):
        return cls.validators.available()

    @classmethod
    def new(cls, zone, name, data, source=None, lenient=False):
        reasons = []
        try:
            name = idna_encode(str(name))
        except IdnaError as e:
            # convert the error into a reason
            reasons.append(str(e))
            name = str(name)

        if ' ' in name or '\t' in name:
            reasons.append('invalid record, whitespace is not allowed')

        fqdn = f'{name}.{zone.name}' if name else zone.name
        context = getattr(data, 'context', None)
        try:
            _type = data['type']
        except KeyError:
            msg = f'Invalid record {idna_decode(fqdn)}, missing type'
            if context:
                msg += f', {context}'
            raise Exception(msg)
        try:
            _class = cls._CLASSES[_type]
        except KeyError:
            msg = f'Unknown record type: "{_type}"'
            if context:
                msg += f', {context}'
            raise Exception(msg)
        reasons.extend(_class.validate(name, fqdn, data))
        try:
            lenient |= data['octodns']['lenient']
        except KeyError:
            pass
        if reasons:
            if lenient:
                cls.log.warning(
                    ValidationError.build_message(fqdn, reasons, context)
                )
            else:
                raise ValidationError(fqdn, reasons, context)
        return _class(zone, name, data, source=source, context=context)

    @classmethod
    def _process_validators(cls, name, fqdn, data):
        return cls.validators.process_record(cls, name, fqdn, data)

    @classmethod
    def validate(cls, name, fqdn, data):
        return cls._process_validators(name, fqdn, data)

    @classmethod
    def from_rrs(cls, zone, rrs, lenient=False, source=None):
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
            record = Record.new(
                zone, name, data, lenient=lenient, source=source
            )
            records.append(record)

        return records

    @classmethod
    def parse_rdata_texts(cls, rdatas):
        return [cls._value_type.parse_rdata_text(r) for r in rdatas]

    def __init__(self, zone, name, data, source=None, context=None):
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
        self.context = context
        self.ttl = int(data['ttl'])

        self.octodns = data.get('octodns', {})

    @property
    def _octodns(self):
        deprecated(
            '`Record._octodns` is DEPRECATED. Use `Record.octodns` instead. Will be removed in 2.0',
            stacklevel=1,
        )
        return self.octodns

    @_octodns.setter
    def _octodns(self, val):
        deprecated(
            '`Record._octodns` is DEPRECATED. Use `Record.octodns` instead. Will be removed in 2.0',
            stacklevel=1,
        )
        self.octodns = val

    def _data(self):
        ret = {'ttl': self.ttl}
        if self.octodns:
            ret['octodns'] = deepcopy(self.octodns)
        if self.context:
            return ContextDict(ret, context=self.context)
        return ret

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
        return self.octodns.get('ignored', False)

    @property
    def excluded(self):
        return self.octodns.get('excluded', [])

    @property
    def included(self):
        return self.octodns.get('included', [])

    def healthcheck_host(self, value=None):
        healthcheck = self.octodns.get('healthcheck', {})
        protocol = self.healthcheck_protocol
        if protocol not in ('HTTP', 'HTTPS'):
            return None
        return healthcheck.get('host', self.fqdn[:-1]) or value

    @property
    def healthcheck_path(self):
        healthcheck = self.octodns.get('healthcheck', {})
        protocol = self.healthcheck_protocol
        if protocol not in ('HTTP', 'HTTPS'):
            return None
        try:
            return healthcheck['path']
        except KeyError:
            return '/_dns'

    @property
    def healthcheck_protocol(self):
        try:
            return self.octodns['healthcheck']['protocol']
        except KeyError:
            return 'HTTPS'

    @property
    def healthcheck_port(self):
        if self.healthcheck_protocol == 'ICMP':
            return None
        try:
            return int(self.octodns['healthcheck']['port'])
        except KeyError:
            return 443

    @property
    def lenient(self):
        return self.octodns.get('lenient', False)

    def changes(self, other, target):
        # We're assuming we have the same name and type if we're being compared
        if self.ttl != other.ttl:
            return Update(self, other)

    def copy(self, zone=None, value=None, values=None, lenient=True):
        # data, via _data(), will preserve context
        data = self.data
        data['type'] = self._type

        # Copy record data but overrides values during copy instead of setting
        # record.value(s) later. Useful when you want to force the new record
        # values to be validated.
        if values is not None:
            data.pop('value', None)
            data['values'] = values
        elif value is not None:
            data.pop('values', None)
            data['value'] = value

        return Record.new(
            zone if zone else self.zone,
            self.name,
            data,
            self.source,
            lenient=lenient,
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


def _process_value_validators(value_type, values, _type):
    return Record.validators.process_values(value_type, values, _type)


class ValuesMixin(object):
    VALIDATORS = [ValuesTypeValidator()]

    @classmethod
    def data_from_rrs(cls, rrs):
        # type and TTL come from the first rr
        rr = rrs[0]
        # values come from parsing the rdata portion of all rrs
        values = [cls._value_type.parse_rdata_text(rr.rdata) for rr in rrs]
        return {'ttl': rr.ttl, 'type': rr._type, 'values': values}

    def __init__(self, zone, name, data, source=None, context=None):
        super().__init__(zone, name, data, source=source, context=context)

        values = data.get('values', data.get('value', []))
        values = values if isinstance(values, (list, tuple)) else [values]
        self.values = sorted(self._value_type.process(values))

    def changes(self, other, target):
        if self.values != other.values:
            return Update(self, other)
        return super().changes(other, target)

    def _data(self):
        ret = super()._data()
        if len(self.values) == 1:
            v = self.values[0]
            if v:
                ret['value'] = getattr(v, 'data', v)
        else:
            values = [getattr(v, 'data', v) for v in self.values if v]
            if len(values) == 1:
                ret['value'] = values[0]
            else:
                ret['values'] = values

        return ret

    @property
    def rr_values(self):
        return self.values

    @property
    def rrs(self):
        return (
            self.fqdn,
            self.ttl,
            self._type,
            [v.rdata_text for v in self.rr_values],
        )

    def __repr__(self):
        values = "', '".join([str(v) for v in self.values])
        klass = self.__class__.__name__
        octodns = ''
        if self.octodns:
            octodns = f', {self.octodns}'
        return f"<{klass} {self._type} {self.ttl}, {self.decoded_fqdn}, ['{values}']{octodns}>"


class ValueMixin(object):
    VALIDATORS = [ValueTypeValidator()]

    @classmethod
    def data_from_rrs(cls, rrs):
        # single value, so single rr only...
        rr = rrs[0]
        return {
            'ttl': rr.ttl,
            'type': rr._type,
            'value': cls._value_type.parse_rdata_text(rr.rdata),
        }

    def __init__(self, zone, name, data, source=None, context=None):
        super().__init__(zone, name, data, source=source, context=context)
        self.value = self._value_type.process(data['value'])

    def changes(self, other, target):
        if self.value != other.value:
            return Update(self, other)
        return super().changes(other, target)

    def _data(self):
        ret = super()._data()
        ret['value'] = getattr(self.value, 'data', self.value)
        return ret

    @property
    def rrs(self):
        return self.fqdn, self.ttl, self._type, [self.value.rdata_text]

    def __repr__(self):
        klass = self.__class__.__name__
        octodns = ''
        if self.octodns:
            octodns = f', {self.octodns}'
        return f'<{klass} {self._type} {self.ttl}, {self.decoded_fqdn}, {self.value}{octodns}>'


Record.register_validator(NameValidator('name-rfc', sets={'legacy', 'strict'}))
Record.register_validator(TtlValidator('ttl-rfc', sets={'legacy', 'strict'}))
Record.register_validator(
    HealthcheckValidator('healthcheck', sets={'legacy', 'strict'})
)
