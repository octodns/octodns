#
#
#


class RecordValidator:
    '''
    Base class for record-level validators.

    Subclasses override ``validate`` to return a list of reason strings
    describing any validation failures. An empty list indicates the record is
    valid. ``record_cls`` is the concrete Record subclass being validated and
    gives validators access to class-level attributes (``_type``,
    ``_value_type``, etc.) when needed. Attributes consulted only by a
    validator should live on the validator itself; ``record_cls`` is only
    the right home for state that's shared across the record and its
    validators.
    '''

    @classmethod
    def validate(cls, record_cls, name, fqdn, data):
        '''
        Validate a record's non-value attributes.

        Parameters
        ----------
        record_cls : type
            The concrete ``Record`` subclass being validated. Validators
            that need access to record class-level attributes (e.g.
            ``_type``, ``_value_type``) should read them from
            ``record_cls`` rather than ``cls``, since ``cls`` is the
            validator class itself. Attributes consulted only by a
            validator should live on the validator, not on
            ``record_cls``.
        name : str
            The record's name relative to its zone (``''`` for the zone
            root). Already ``idna_encode``'d.
        fqdn : str
            The record's fully-qualified domain name (``name`` + zone name).
        data : dict
            The raw record config dict (as loaded from YAML/JSON) including
            ``ttl``, ``type``, ``value``/``values``, and any type-specific
            fields like ``dynamic``, ``geo``, or ``octodns``.

        Returns
        -------
        list[str]
            A list of human-readable reason strings describing validation
            failures. Must return an empty list when the record is valid.
            Reasons from multiple validators are concatenated by the caller,
            so each reason must stand alone without context from the others.

        Notes
        -----
        Implementations must not raise on invalid input — all failures are
        reported via the returned list. Reason strings are surfaced
        verbatim in ``ValidationError`` messages, so phrasing and
        punctuation should be stable across releases.
        '''
        return []


class ValueValidator:
    '''
    Base class for value-level validators.

    Subclasses override ``validate`` to return a list of reason strings
    describing any validation failures. An empty list indicates the value is
    valid. ``value_cls`` is the concrete value class being validated.
    Attributes consulted only by a validator should live on the validator
    itself; ``value_cls`` is only the right home for state that's shared
    across the value class and its validators.
    '''

    @classmethod
    def validate(cls, value_cls, data, _type):
        '''
        Validate a record's rdata values.

        Parameters
        ----------
        value_cls : type
            The concrete value class being validated (e.g. ``MxValue``,
            ``_Ipv4Value``). Validators that need access to value
            class-level attributes (e.g. ``VALID_ALGORITHMS``,
            ``_address_type``) should read them from ``value_cls``
            rather than ``cls``, since ``cls`` is the validator class
            itself. Attributes consulted only by a validator should
            live on the validator, not on ``value_cls``.
        data : list | tuple | str | dict
            The rdata to validate. For multi-value record types this is a
            list/tuple of value dicts or strings; for single-value types
            it may be a bare value. Most validators iterate ``data``
            directly — when a validator needs to accept either form it
            should normalize with ``if not isinstance(data, (list,
            tuple)): data = (data,)``.
        _type : str
            The record type string (e.g. ``'MX'``, ``'A'``). Passed
            through to helpers like ``validate_target_fqdn`` which format
            it into their reason strings.

        Returns
        -------
        list[str]
            A list of human-readable reason strings describing validation
            failures. Must return an empty list when the values are
            valid. Reasons from multiple validators are concatenated by
            the caller, so each reason must stand alone without context
            from the others.

        Notes
        -----
        Implementations must not raise on invalid input — all failures
        are reported via the returned list. Reason strings are surfaced
        verbatim in ``ValidationError`` messages, so phrasing and
        punctuation should be stable across releases.
        '''
        return []
