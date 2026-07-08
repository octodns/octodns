#
#
#

from collections import defaultdict
from logging import getLogger

from ..deprecation import deprecated
from .exception import RecordException


class ValidatorRegistry:
    log = getLogger('Record')

    def __init__(self):
        self.available_record = defaultdict(dict)
        self.available_value = defaultdict(dict)
        self.active_record = defaultdict(dict)
        self.active_value = defaultdict(dict)
        self.configured = False

    def register(self, validator, types=None, replace=False):
        if isinstance(validator, RecordValidator):
            registry = self.available_record
        elif isinstance(validator, ValueValidator):
            registry = self.available_value
        else:
            raise RecordException(
                f'{validator.__class__.__name__} must be a RecordValidator or ValueValidator instance'
            )
        keys = ('*',) if types is None else types
        for key in keys:
            bucket = registry[key]
            if validator.id in bucket:
                if not replace:
                    raise RecordException(
                        f'Validator id "{validator.id}" already registered for "{key}"'
                    )
                self.log.info(
                    'register: overriding built-in validator id "%s" for "%s"',
                    validator.id,
                    key,
                )
            bucket[validator.id] = validator

    def enable_sets(self, sets):
        self.configured = True
        self.reset_active()
        sets = set(sets)
        for available, active in (
            (self.available_record, self.active_record),
            (self.available_value, self.active_value),
        ):
            for _type, validators in available.items():
                for validator in validators.values():
                    if validator.sets is None or sets & validator.sets:
                        active[_type][validator.id] = validator

    def enable(self, id, types=None):
        validator = None
        for available in (self.available_record, self.available_value):
            for bucket in available.values():
                if id in bucket:
                    validator = bucket[id]
                    break
            if validator is not None:
                break
        if validator is None:
            raise RecordException(f'Unknown validator id "{id}"')
        active = (
            self.active_record
            if isinstance(validator, RecordValidator)
            else self.active_value
        )
        keys = ('*',) if types is None else types
        for key in keys:
            active[key][id] = validator

    def disable(self, validator_id, types=None):
        if validator_id.startswith('_'):
            raise RecordException(
                f'Cannot disable bridge validator "{validator_id}"'
            )
        removed = 0
        if types is None:
            for registry in (self.active_record, self.active_value):
                for bucket in registry.values():
                    if bucket.pop(validator_id, None) is not None:
                        removed += 1
        else:
            for key in types:
                for registry in (self.active_record, self.active_value):
                    if (
                        key in registry
                        and registry[key].pop(validator_id, None) is not None
                    ):
                        removed += 1
        return removed

    def reset_active(self):
        self.active_record.clear()
        self.active_value.clear()

    def registered(self):
        return {
            'record': {
                k: list(v.values()) for k, v in self.active_record.items()
            },
            'value': {
                k: list(v.values()) for k, v in self.active_value.items()
            },
        }

    def available(self):
        return {
            'record': {
                k: list(v.values()) for k, v in self.available_record.items()
            },
            'value': {
                k: list(v.values()) for k, v in self.available_value.items()
            },
        }

    def process_record(self, record_cls, name, fqdn, data, disabled=None):
        if not self.configured:
            self.log.warning(
                '_process_validators: no validators configured, automatically enabling legacy set'
            )
            self.enable_sets({'legacy'})
        disabled = disabled or {}
        reasons = []
        for key in ('*', record_cls._type):
            skip = disabled.get(key, ())
            for validator in self.active_record.get(key, {}).values():
                if validator.id in skip and not validator.id.startswith('_'):
                    continue
                try:
                    reasons.extend(
                        _as_reason(r, validator.id)
                        for r in validator.validate(
                            record_cls, name, fqdn, data, disabled=disabled
                        )
                    )
                except TypeError as e:
                    if "unexpected keyword argument 'disabled'" not in str(e):
                        raise
                    deprecated(
                        f'`validate` without the `disabled` param is DEPRECATED. Will be removed in 2.0. Class {validator.__class__.__name__}',
                        stacklevel=3,
                    )
                    reasons.extend(
                        _as_reason(r, validator.id)
                        for r in validator.validate(
                            record_cls, name, fqdn, data
                        )
                    )
        return reasons

    def process_values(self, value_type, values, _type, disabled=None):
        disabled = disabled or {}
        reasons = []
        legacy = getattr(value_type, 'validate', None)
        if legacy is not None:
            deprecated(
                f'`{value_type.__name__}.validate` classmethod is DEPRECATED. Add a ValueValidator to `VALIDATORS` instead. Will be removed in 2.0',
                stacklevel=3,
            )
            legacy_id = f'{value_type.__name__}.validate'
            reasons.extend(
                _as_reason(r, legacy_id, warn=False)
                for r in legacy(values, _type)
            )
        for key in ('*', _type):
            skip = disabled.get(key, ())
            for validator in self.active_value.get(key, {}).values():
                if validator.id in skip and not validator.id.startswith('_'):
                    continue
                reasons.extend(
                    _as_reason(r, validator.id)
                    for r in validator.validate(value_type, values, _type)
                )
        return reasons


class ValidationReason(str):
    '''
    A single validation failure reason.

    Behaves as a plain ``str`` (its content is the bare, human-readable
    reason text) so existing code that compares or joins reasons as
    strings keeps working unchanged. In addition it carries the set of
    ``records`` the failure applies to and the ``validator_id`` of the
    validator that produced it, which ``__str__`` uses to append context
    and ``, via: <validator_id>`` attribution — richer output that only
    appears where a caller explicitly renders with ``str(reason)``
    (e.g. in ``ValidationError`` messages); plain string joins/comparisons
    see only the bare reason.
    '''

    def __new__(cls, reason, records=(), validator_id=None):
        # str content is fixed at __new__ time (str is immutable), so this
        # must exist to make the content `reason` alone; otherwise str.__new__
        # would be called with `records`/`validator_id` too and raise a
        # TypeError.
        return super().__new__(cls, reason)

    def __init__(self, reason, records=(), validator_id=None):
        if validator_id is None:
            deprecated(
                'omitting `validator_id` is DEPRECATED. It will be a required parameter as of 2.0',
                stacklevel=3,
            )
        self.validator_id = validator_id
        self.reason = reason
        self.records = set(records)

    @property
    def lenient(self):
        return bool(self.records) and all(r.lenient for r in self.records)

    def __str__(self):
        msg = self.reason
        contexts = {
            r.context for r in self.records if getattr(r, 'context', None)
        }
        if contexts:
            msg += f" ({', '.join(sorted(contexts))})"
        if self.validator_id:
            msg += f', via: {self.validator_id}'
        return msg

    def __repr__(self):
        return self.reason


def _as_reason(reason, validator_id, warn=True):
    if not isinstance(reason, ValidationReason):
        if warn:
            deprecated(
                'validators returning `str` reasons is DEPRECATED; return `ValidationReason`. Will be required in 2.0',
                stacklevel=4,
            )
        return ValidationReason(reason, validator_id=validator_id)
    if reason.validator_id is None:
        reason.validator_id = validator_id
    return reason


class RecordValidator:
    '''
    Base class for record-level validators.

    Subclasses override ``validate`` to return a list of reason strings
    describing any validation failures. An empty list indicates the record is
    valid. ``record_cls`` is the concrete Record subclass being validated and
    gives validators access to class-level attributes (``_type``,
    ``_value_type``, etc.) when needed. Attributes consulted only by a
    validator should live on the validator instance (``self``);
    ``record_cls`` is only the right home for state that's shared across
    the record and its validators.

    Every validator instance has a non-empty ``id`` — a short, stable,
    kebab-case identifier used to reference the validator in the registry
    (e.g. for config-driven disabling). Built-ins are constructed at
    import time with their well-known id (e.g. ``NameValidator('name')``).
    Config-registered validators receive their config key as ``id``
    automatically. Underscore-prefixed ids (e.g. ``_values-type``) are
    reserved for framework-internal bridge validators that must always
    run.

    A config-registered validator whose id matches a built-in's
    *replaces* that built-in in the registry — e.g. defining a
    ``validators:`` entry named ``name-rfc`` swaps out the built-in
    ``NameValidator`` for the custom instance. This is the supported way
    to tweak a built-in's parameters without disabling it and inventing a
    new id.
    '''

    def __init__(self, id, sets=None):
        '''
        :param id: Non-empty identifier for this validator instance. Used
                   to look up the validator in the registry and to
                   reference it in config (for enabling/disabling, etc.).
        :param sets: Iterable of set names this validator belongs to, or
                     ``None`` (the default) to always activate regardless of
                     ``manager.enabled``. Pass an explicit set such as
                     ``sets={'legacy'}`` to opt into set-based filtering.
        '''
        if not id:
            raise ValueError(
                f'{self.__class__.__name__} requires a non-empty id'
            )
        self.id = id
        self.sets = set(sets) if sets is not None else None

    def validate(self, record_cls, name, fqdn, data, disabled=None):
        '''
        Validate a record's non-value attributes.

        Parameters
        ----------
        record_cls : type
            The concrete ``Record`` subclass being validated. Validators
            that need access to record class-level attributes (e.g.
            ``_type``, ``_value_type``) should read them from
            ``record_cls``. Per-instance configuration should live on
            ``self``, not on ``record_cls``.
        name : str
            The record's name relative to its zone (``''`` for the zone
            root). Already ``idna_encode``'d.
        fqdn : str
            The record's fully-qualified domain name (``name`` + zone name).
        data : dict
            The raw record config dict (as loaded from YAML/JSON) including
            ``ttl``, ``type``, ``value``/``values``, and any type-specific
            fields like ``dynamic``, ``geo``, or ``octodns``.
        disabled : dict or None
            The zone's per-type map of disabled validator ids (``record_cls
            ._type`` or ``'*'`` -> set of ids), as configured via the zone's
            ``validators.record.disable_validators``. Most validators can
            ignore this; it only matters to validators that themselves
            dispatch to other validators (e.g. value-type bridges, ``geo``
            and ``dynamic`` validators), which must forward it along so the
            disabled ids are honored down the chain.

        Returns
        -------
        list[ValidationReason]
            A list of ``ValidationReason`` objects describing validation
            failures — construct each with ``ValidationReason(reason,
            validator_id=self.id)``. Must return an empty list when the
            record is valid. Reasons from multiple validators are
            concatenated by the caller, so each reason must stand alone
            without context from the others. Returning bare ``str``
            reasons is DEPRECATED — the registry wraps them in
            ``ValidationReason`` and emits a deprecation warning; support
            will be removed in 2.0.

        Notes
        -----
        Implementations must not raise on invalid input — all failures are
        reported via the returned list. Reason text is surfaced verbatim
        in ``ValidationError`` messages, so phrasing and punctuation
        should be stable across releases.

        Third-party validators that predate the ``disabled`` parameter and
        implement ``validate(self, record_cls, name, fqdn, data)`` continue to
        work: the caller detects the ``TypeError`` and falls back to calling
        without it, emitting a deprecation warning. Support for the
        parameter-less form will be removed in 2.0.
        '''
        return []


class ValueValidator:
    '''
    Base class for value-level validators.

    Subclasses override ``validate`` to return a list of ``ValidationReason``
    objects describing any validation failures. An empty list indicates the value is
    valid. ``value_cls`` is the concrete value class being validated.
    Per-instance configuration should live on the validator instance
    (``self``); ``value_cls`` is only the right home for state that's
    shared across the value class and its validators.

    Every validator instance has a non-empty ``id`` — a short, stable,
    kebab-case identifier used to reference the validator in the registry
    (e.g. for config-driven disabling). Built-ins are constructed at
    import time with their well-known id (e.g. ``MxValueValidator('mx-value')``).
    Config-registered validators receive their config key as ``id``
    automatically. Underscore-prefixed ids are reserved for
    framework-internal bridge validators that must always run.

    A config-registered validator whose id matches a built-in's
    *replaces* that built-in in the registry. Built-in value validators
    are registered per record ``type`` (e.g. ``mx-value`` under ``MX``),
    so overriding one requires passing the matching ``types:`` in config
    — a bare override with no ``types`` registers under ``'*'`` instead
    and does not replace the type-specific built-in.
    '''

    def __init__(self, id, sets=None):
        '''
        :param id: Non-empty identifier for this validator instance. Used
                   to look up the validator in the registry and to
                   reference it in config (for enabling/disabling, etc.).
        :param sets: Iterable of set names this validator belongs to, or
                     ``None`` (the default) to always activate regardless of
                     ``manager.enabled``. Pass an explicit set such as
                     ``sets={'legacy'}`` to opt into set-based filtering.
        '''
        if not id:
            raise ValueError(
                f'{self.__class__.__name__} requires a non-empty id'
            )
        self.id = id
        self.sets = set(sets) if sets is not None else None

    def validate(self, value_cls, data, _type):
        '''
        Validate a record's rdata values.

        Parameters
        ----------
        value_cls : type
            The concrete value class being validated (e.g. ``MxValue``,
            ``_Ipv4Value``). Validators that need access to value
            class-level attributes (e.g. ``VALID_ALGORITHMS``,
            ``_address_type``) should read them from ``value_cls``.
            Per-instance configuration should live on ``self``, not on
            ``value_cls``.
        data : list | tuple | str | dict
            The rdata to validate. For multi-value record types this is a
            list/tuple of value dicts or strings; for single-value types
            it may be a bare value. Most validators iterate ``data``
            directly — when a validator needs to accept either form it
            should normalize with ``if not isinstance(data, (list,
            tuple)): data = (data,)``.
        _type : str
            The record type string (e.g. ``'MX'``, ``'A'``). Passed
            through to helpers like ``_check_target_format`` which format
            it into their reason strings.

        Returns
        -------
        list[ValidationReason]
            A list of ``ValidationReason`` objects describing validation
            failures — construct each with ``ValidationReason(reason,
            validator_id=self.id)``. Must return an empty list when the
            values are valid. Reasons from multiple validators are
            concatenated by the caller, so each reason must stand alone
            without context from the others. Returning bare ``str``
            reasons is DEPRECATED — the registry wraps them in
            ``ValidationReason`` and emits a deprecation warning; support
            will be removed in 2.0.

        Notes
        -----
        Implementations must not raise on invalid input — all failures
        are reported via the returned list. Reason strings are surfaced
        verbatim in ``ValidationError`` messages, so phrasing and
        punctuation should be stable across releases.
        '''
        return []
