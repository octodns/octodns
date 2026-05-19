#
#
#
#

from __future__ import annotations

from .base import Record
from .chunked import _ChunkedValue, _ChunkedValuesMixin


class TxtValue(_ChunkedValue):
    pass


class TxtRecord(_ChunkedValuesMixin, Record):
    REFERENCES: tuple[str, ...] = (
        'https://datatracker.ietf.org/doc/html/rfc1035',
        'https://datatracker.ietf.org/doc/html/rfc1464',
        'https://datatracker.ietf.org/doc/html/rfc6763',
    )
    _type = 'TXT'  # type: ignore[misc]
    _value_type = TxtValue  # type: ignore[misc]


Record.register_type(TxtRecord)
