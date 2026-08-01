#
#
#

from ..deprecation import deprecated
from .exception import RecordException


class RrParseError(RecordException):
    def __init__(self, message='failed to parse string value as RR text'):
        super().__init__(message)


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


class Rrset(object):
    '''A grouped DNS resource-record set in presentation format.

    The carrier represents one owner name, type, TTL, and an ordered list of
    RDATA presentation-format strings. DNS class is not stored and is
    implicitly Internet (``IN``). Unlike the deprecated :class:`Rr`, one
    ``Rrset`` contains all values for the owner/type pair.

    :param str name: fully-qualified owner name
    :param str _type: DNS record type shared by all values
    :param int ttl: time to live in seconds shared by all values
    :param collections.abc.Iterable rdatas: RDATA values in DNS master-file
        presentation format
    '''

    def __init__(self, name, _type, ttl, rdatas):
        self.name = name
        self._type = _type
        self.ttl = ttl
        self.rdatas = list(rdatas)

    def __repr__(self):
        return f'Rrset<{self.name}, {self._type}, {self.ttl}, {self.rdatas}'
