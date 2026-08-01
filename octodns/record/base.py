#
#
#

from collections import defaultdict
from copy import deepcopy
from functools import cache
from logging import getLogger

from ..context import ContextDict
from ..deprecation import deprecated
from ..equality import EqualityTupleMixin
from ..idna import IdnaError, idna_decode, idna_encode
from .change import Update
from .exception import RecordException, ValidationError
from .rr import Rrset
from .validator import RecordValidator, ValidationReason, ValidatorRegistry


def unquote(s):
    if s and s[0] in ('"', "'"):
        return s[1:-1]
    return s


def _deprecated_parse_rdata_text(value_type, replacement=None):
    replacement = replacement or f'{value_type.__name__}.from_rdata_text()'
    deprecated(
        f'`{value_type.__name__}.parse_rdata_text` is DEPRECATED. Use '
        f'`{replacement}` instead. Will be removed in 2.0.',
        stacklevel=4,
    )


def _deprecated_rdata_text(value, replacement=None):
    value_type = value.__class__
    replacement = replacement or f'{value_type.__name__}.to_rdata_text()'
    deprecated(
        f'`{value_type.__name__}.rdata_text` is DEPRECATED. Use '
        f'`{replacement}` instead. Will be removed in 2.0.',
        stacklevel=4,
    )


def _mro_owner(value_type, name):
    for index, owner in enumerate(value_type.__mro__):
        if name in owner.__dict__:
            return index
    return None


@cache
def _value_from_rdata_text_uses_legacy(value_type):
    new_owner = _mro_owner(value_type, 'from_rdata_text')
    legacy_owner = _mro_owner(value_type, 'parse_rdata_text')
    return new_owner is None or (
        legacy_owner is not None and legacy_owner < new_owner
    )


def value_from_rdata_text(value_type, rdata):
    '''Convert one presentation-format RDATA string to internal value data.

    Dispatch prefers ``from_rdata_text()`` while retaining compatibility with
    third-party value types that only implement ``parse_rdata_text()``.

    :param type value_type: record value type performing the conversion
    :param str rdata: one RDATA value in presentation format
    :returns: internal data suitable for constructing ``value_type``
    '''
    if not _value_from_rdata_text_uses_legacy(value_type):
        return value_type.from_rdata_text(rdata)
    # Intentionally identify the octoDNS conversion path. This warning is
    # about the legacy implementation on the value type, not its caller.
    deprecated(
        f'`{value_type.__name__}.parse_rdata_text` is DEPRECATED. '
        'Implement `from_rdata_text()` instead. Will be removed in 2.0.',
        stacklevel=3,
    )
    return value_type.parse_rdata_text(rdata)


@cache
def _value_to_rdata_text_uses_legacy(value_type):
    new_owner = _mro_owner(value_type, 'to_rdata_text')
    legacy_owner = _mro_owner(value_type, 'rdata_text')
    return new_owner is None or (
        legacy_owner is not None and legacy_owner < new_owner
    )


def value_to_rdata_text(value):
    '''Render one logical value as one presentation-format RDATA string.

    Dispatch prefers ``to_rdata_text()`` while retaining compatibility with
    third-party values that only implement the ``rdata_text`` property.

    :param object value: one record value object
    :returns: one RDATA value in presentation format
    :rtype: str
    '''
    value_type = value.__class__
    if not _value_to_rdata_text_uses_legacy(value_type):
        return value.to_rdata_text()
    # Intentionally identify the octoDNS conversion path. This warning is
    # about the legacy implementation on the value type, not its caller.
    deprecated(
        f'`{value_type.__name__}.rdata_text` is DEPRECATED. '
        'Implement `to_rdata_text()` instead. Will be removed in 2.0.',
        stacklevel=3,
    )
    return value.rdata_text


class NameValidator(RecordValidator):
    '''
    Validates record name and FQDN shape: rejects the legacy ``@`` alias,
    enforces the 253-char total FQDN length and 63-char per-label length
    limits from RFC 1035, and flags empty/double-dot labels.
    '''

    def validate(self, record_cls, name, fqdn, data, disabled=None):
        reasons = []
        if name == '@':
            reasons.append(
                ValidationReason(
                    'invalid name "@", use "" instead', validator_id=self.id
                )
            )
        n = len(fqdn)
        if n > 253:
            reasons.append(
                ValidationReason(
                    f'invalid fqdn, "{idna_decode(fqdn)}" is too long at {n} chars, max is 253',
                    validator_id=self.id,
                )
            )
        for label in name.split('.'):
            n = len(label)
            if n > 63:
                reasons.append(
                    ValidationReason(
                        f'invalid label, "{label}" is too long at {n} chars, max is 63',
                        validator_id=self.id,
                    )
                )
        # in the case of endswith there's an implicit second . from the Zone
        if '..' in name or name.endswith('.'):
            reasons.append(
                ValidationReason(
                    f'invalid name, double `.` in "{idna_decode(fqdn)}"',
                    validator_id=self.id,
                )
            )
        # TODO: look at the idna lib for a lot more potential validations...
        return reasons


class TtlValidator(RecordValidator):
    '''
    Validates that the record has a ttl and that it is a non-negative
    integer.
    '''

    def validate(self, record_cls, name, fqdn, data, disabled=None):
        reasons = []
        try:
            ttl = int(data['ttl'])
            if ttl < 0:
                reasons.append(
                    ValidationReason('invalid ttl', validator_id=self.id)
                )
        except KeyError:
            reasons.append(
                ValidationReason('missing ttl', validator_id=self.id)
            )
        return reasons


class HealthcheckValidator(RecordValidator):
    '''
    Validates the optional ``octodns.healthcheck.protocol`` setting, if
    present, is one of the supported protocols.
    '''

    def validate(self, record_cls, name, fqdn, data, disabled=None):
        reasons = []
        try:
            if data['octodns']['healthcheck']['protocol'] not in (
                'HTTP',
                'HTTPS',
                'ICMP',
                'TCP',
                'UDP',
            ):
                reasons.append(
                    ValidationReason(
                        'invalid healthcheck protocol', validator_id=self.id
                    )
                )
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

    def validate(self, record_cls, name, fqdn, data, disabled=None):
        return _process_value_validators(
            record_cls._value_type,
            data.get('value', None),
            record_cls._type,
            disabled=disabled,
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

    def validate(self, record_cls, name, fqdn, data, disabled=None):
        values = data.get('values', data.get('value', []))
        values = (
            values
            if isinstance(values, (list, tuple))
            else ([] if values is None else [values])
        )
        return _process_value_validators(
            record_cls._value_type, values, record_cls._type, disabled=disabled
        )


class Record(EqualityTupleMixin):
    log = getLogger('Record')

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if 'validate' in cls.__dict__:
            deprecated(
                f'`{cls.__name__}.validate` override is DEPRECATED. Add a RecordValidator to `VALIDATORS` instead. Will be removed in 2.0',
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
    def register_validator(cls, validator, types=None, replace=False):
        cls.validators.register(validator, types=types, replace=replace)

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
        disabled = zone.disabled_record_validators
        try:
            reasons.extend(_class.validate(name, fqdn, data, disabled=disabled))
        except TypeError as e:
            if "unexpected keyword argument 'disabled'" not in str(e):
                raise
            deprecated(
                f'`validate` without the `disabled` param is DEPRECATED. Will be removed in 2.0. Class {_class.__name__}',
                stacklevel=3,
            )
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
    def _process_validators(cls, name, fqdn, data, disabled=None):
        return cls.validators.process_record(
            cls, name, fqdn, data, disabled=disabled
        )

    @classmethod
    def validate(cls, name, fqdn, data, disabled=None):
        return cls._process_validators(name, fqdn, data, disabled=disabled)

    @classmethod
    def from_rrs(cls, zone, rrs, lenient=False, source=None):
        '''Create records from deprecated, individual :class:`~octodns.record.rr.Rr` objects.

        The flat input is grouped by owner name and type and converted with
        each record class's legacy ``data_from_rrs()`` implementation. Input
        order is retained within each group and output records are ordered
        deterministically by owner name and type. ``lenient`` and ``source``
        are passed unchanged to :meth:`Record.new`.

        :param octodns.zone.Zone zone: zone containing the records
        :param collections.abc.Iterable rrs: individual
            :class:`~octodns.record.rr.Rr` objects whose ``rdata`` attributes
            are RDATA presentation-format strings
        :param bool lenient: allow records that fail validation
        :param object source: source assigned to every returned record
        :returns: zero or more octoDNS records
        :rtype: list[Record]

        .. deprecated:: 1.22.0
           Use :meth:`from_rrsets`. ``Record.from_rrs`` will be removed in
           2.0.
        '''
        deprecated(
            '`Record.from_rrs` is DEPRECATED. Use `Record.from_rrsets()` '
            'instead. Will be removed in 2.0.',
            stacklevel=3,
        )
        # group records by name & type so that multiple rdatas can be combined
        # into a single record when needed
        grouped = defaultdict(list)
        for rr in rrs:
            grouped[(rr.name, rr._type)].append(rr)

        records = []
        for _, grouped_rrs in sorted(grouped.items()):
            first = grouped_rrs[0]
            name = zone.hostname_from_fqdn(first.name)
            record_class = cls._CLASSES[first._type]
            data = record_class.data_from_rrs(grouped_rrs)
            records.append(
                Record.new(zone, name, data, lenient=lenient, source=source)
            )
        return records

    @classmethod
    def _record_from_rrset(cls, zone, rrset, lenient=False, source=None):
        if not rrset.rdatas:
            raise RecordException(
                f'Invalid Rrset {rrset.name} {rrset._type}: at least one '
                'RDATA value is required'
            )
        try:
            record_class = cls._CLASSES[rrset._type]
        except KeyError:
            raise RecordException(
                f'Unknown record type: "{rrset._type}"'
            ) from None
        name = zone.hostname_from_fqdn(rrset.name)
        data = record_class.data_from_rrset(rrset)
        return Record.new(zone, name, data, lenient=lenient, source=source)

    @classmethod
    def from_rrset(cls, zone, rrset, lenient=False, source=None):
        '''Create one octoDNS record from one grouped RRset.

        ``rrset`` contains one owner, type, TTL, and one or more RDATA values
        in DNS master-file presentation format. DNS class is implicitly
        Internet (``IN``). The returned record exposes octoDNS internal-format
        values. ``lenient`` and ``source`` are passed unchanged to
        :meth:`Record.new`.

        Provider example::

            rrset = Rrset(
                'www.example.com.', 'A', 300, ['192.0.2.1', '192.0.2.2']
            )
            record = Record.from_rrset(zone, rrset, source=provider)

        :param octodns.zone.Zone zone: zone containing the record
        :param octodns.record.rr.Rrset rrset: exactly one grouped RRset
        :param bool lenient: allow a record that fails validation
        :param object source: source assigned to the returned record
        :returns: exactly one octoDNS record
        :rtype: Record
        :raises octodns.record.exception.RecordException: if the RRset is
            invalid, a single-value record contains multiple RDATA values, or
            the type is not registered
        :raises octodns.record.exception.ValidationError: if the converted
            internal record data fails validation and ``lenient`` is false
        '''
        return cls._record_from_rrset(
            zone, rrset, lenient=lenient, source=source
        )

    @classmethod
    def from_rrsets(cls, zone, rrsets, lenient=False, source=None):
        '''Create records from grouped RRsets.

        Each :class:`~octodns.record.rr.Rrset` contains RDATA
        presentation-format strings and implicitly uses Internet (``IN``)
        class. At most one RRset may occur for each owner-name/type pair.
        Results are sorted deterministically by owner name and type. Empty
        input returns an empty list. ``lenient`` and ``source`` are passed
        unchanged to every :meth:`Record.new` call.

        :param octodns.zone.Zone zone: zone containing the records
        :param collections.abc.Iterable rrsets: grouped
            :class:`~octodns.record.rr.Rrset` objects
        :param bool lenient: allow records that fail validation
        :param object source: source assigned to every returned record
        :returns: zero or more octoDNS records in owner-name/type order
        :rtype: list[Record]
        :raises octodns.record.exception.RecordException: if an RRset is
            invalid, a single-value record contains multiple RDATA values, a
            type is not registered, or an owner-name/type pair occurs more
            than once
        :raises octodns.record.exception.ValidationError: if converted
            internal record data fails validation and ``lenient`` is false
        '''
        grouped = {}
        for rrset in rrsets:
            key = (rrset.name, rrset._type)
            if key in grouped:
                raise RecordException(
                    f'Duplicate Rrset {rrset.name} {rrset._type}'
                )
            grouped[key] = rrset
        return [
            cls._record_from_rrset(
                zone, grouped[key], lenient=lenient, source=source
            )
            for key in sorted(grouped)
        ]

    @classmethod
    def parse_rdata_texts(cls, rdatas):
        return [value_from_rdata_text(cls._value_type, r) for r in rdatas]

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

    def to_rrset(self):
        '''Render this record as one grouped RRset.

        Values exposed by this record in octoDNS internal format are converted
        into deterministic RDATA presentation-format strings. The returned
        :class:`~octodns.record.rr.Rrset` contains this record's fully-qualified
        owner name, type, and TTL; DNS class is implicitly Internet (``IN``).

        Provider example::

            rrset = record.to_rrset()
            provider_values = rrset.rdatas

        :returns: exactly one grouped RRset
        :rtype: octodns.record.rr.Rrset
        '''
        return self._to_rrset(self._rdatas())

    def _to_rrset(self, rdatas):
        return Rrset(self.fqdn, self._type, self.ttl, rdatas)

    def _legacy_rdatas(self):
        return self._rdatas()

    @property
    def rrs(self):
        '''Return the deprecated legacy RRset tuple.

        The plain tuple order remains ``(name, ttl, type, rdatas)`` and differs
        from the named :class:`~octodns.record.rr.Rrset` constructor order.

        :returns: owner name, TTL, type, and a list of RDATA presentation text
        :rtype: tuple

        .. deprecated:: 1.22.0
           Use :meth:`to_rrset`. ``Record.rrs`` will be removed in 2.0.
        '''
        deprecated(
            '`Record.rrs` is DEPRECATED. Use `Record.to_rrset()` instead. '
            'Will be removed in 2.0.',
            stacklevel=3,
        )
        rrset = self._to_rrset(self._legacy_rdatas())
        return rrset.name, rrset.ttl, rrset._type, rrset.rdatas

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


def _process_value_validators(value_type, values, _type, disabled=None):
    return Record.validators.process_values(
        value_type, values, _type, disabled=disabled
    )


class ValuesMixin(object):
    VALIDATORS = [ValuesTypeValidator()]

    @classmethod
    def data_from_rrs(cls, rrs):
        # type and TTL come from the first rr
        rr = rrs[0]
        # values come from parsing the rdata portion of all rrs
        values = [
            value_from_rdata_text(cls._value_type, rr.rdata) for rr in rrs
        ]
        return {'ttl': rr.ttl, 'type': rr._type, 'values': values}

    @classmethod
    def data_from_rrset(cls, rrset):
        values = [
            value_from_rdata_text(cls._value_type, rdata)
            for rdata in rrset.rdatas
        ]
        return {'ttl': rrset.ttl, 'type': rrset._type, 'values': values}

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

    def _rdatas(self):
        return [value_to_rdata_text(v) for v in self.rr_values]

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
            'value': value_from_rdata_text(cls._value_type, rr.rdata),
        }

    @classmethod
    def data_from_rrset(cls, rrset):
        if len(rrset.rdatas) != 1:
            raise RecordException(
                f'Invalid Rrset {rrset.name} {rrset._type}: exactly one '
                'RDATA value is required for a single-value record'
            )
        return {
            'ttl': rrset.ttl,
            'type': rrset._type,
            'value': value_from_rdata_text(cls._value_type, rrset.rdatas[0]),
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

    def _rdatas(self):
        return [value_to_rdata_text(self.value)]

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
