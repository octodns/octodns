#
#
#

from ..deprecation import deprecated
from ..equality import EqualityTupleMixin
from .exception import RecordException


class RdataParseError(RecordException):
    '''Raised when RDATA presentation text cannot be parsed.

    :param str message: description of the parse failure
    '''

    def __init__(
        self, message='failed to parse string value as RDATA presentation text'
    ):
        super().__init__(message)


# ``RrParseError`` is retained as an identity-preserving compatibility alias
# throughout 1.x. It will be removed in 2.0.
RrParseError = RdataParseError


class Rr(object):
    '''A deprecated carrier for one DNS resource record.

    ``rdata`` is one RDATA presentation-format string. The owner ``name``,
    record ``_type``, and ``ttl`` apply only to that value and the DNS class is
    implicitly Internet (``IN``).

    :param str name: fully-qualified owner name
    :param str _type: DNS record type
    :param int ttl: time to live in seconds
    :param str rdata: one RDATA value in DNS master-file presentation format

    .. deprecated:: 1.22.0
       Use :class:`Rrset`, which groups all RDATA values for an owner and type.
       ``Rr`` and :meth:`octodns.record.base.Record.from_rrs` will be removed
       in 2.0.
    '''

    def __init__(self, name, _type, ttl, rdata):
        deprecated(
            '`Rr` is DEPRECATED. Use `Rrset` instead. Will be removed in 2.0.',
            stacklevel=3,
        )
        self.name = name
        self._type = _type
        self.ttl = ttl
        self.rdata = rdata

    def __repr__(self):
        return f'Rr<{self.name}, {self._type}, {self.ttl}, {self.rdata}'


class Rrset(EqualityTupleMixin):
    '''A grouped DNS resource-record set in presentation format.

    The carrier represents one owner name, type, TTL, and an ordered list of
    RDATA presentation-format strings. DNS class is not stored and is
    implicitly Internet (``IN``). Unlike the deprecated :class:`Rr`, one
    ``Rrset`` contains all values for the owner/type pair. Equality and
    ordering compare the name, type, TTL, and ordered RDATA values.

    :param str name: fully-qualified owner name
    :param str _type: DNS record type shared by all values
    :param int ttl: time to live in seconds shared by all values
    :param collections.abc.Iterable rdatas: RDATA values in DNS master-file
        presentation format
    :raises octodns.record.exception.RecordException: if ``rdatas`` is not a
        non-string iterable, is empty, or contains a non-string value
    '''

    def __init__(self, name, _type, ttl, rdatas):
        self.name = name
        self._type = _type
        self.ttl = ttl
        if isinstance(rdatas, str):
            raise RecordException(
                f'Invalid Rrset {name} {_type}: RDATA values must be a '
                'non-string iterable of strings'
            )
        try:
            self.rdatas = list(rdatas)
        except TypeError:
            raise RecordException(
                f'Invalid Rrset {name} {_type}: RDATA values must be a '
                'non-string iterable of strings'
            ) from None
        if not self.rdatas:
            raise RecordException(
                f'Invalid Rrset {name} {_type}: at least one RDATA value is '
                'required'
            )
        for index, rdata in enumerate(self.rdatas):
            if not isinstance(rdata, str):
                raise RecordException(
                    f'Invalid Rrset {name} {_type}: RDATA value at index '
                    f'{index} must be a string'
                )

    def _equality_tuple(self):
        return self.name, self._type, self.ttl, tuple(self.rdatas)

    def __repr__(self):
        return f'Rrset<{self.name}, {self._type}, {self.ttl}, {self.rdatas}>'
