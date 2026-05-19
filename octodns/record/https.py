#
# This file describes the HTTPS records as defined in RFC 9460
# It also supports the 'ech' SvcParam as defined in draft-ietf-tls-svcb-ech-02
#

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base import Record, ValuesMixin
from .svcb import (
    SvcbValueBestPracticeValidator,
    SvcbValueValidator,
    _SvcbValueBase,
)

if TYPE_CHECKING:
    pass


class HttpsValue(_SvcbValueBase):
    VALIDATORS: list[Any] = [
        SvcbValueValidator('https-value-rfc', sets={'legacy', 'strict'}),
        SvcbValueBestPracticeValidator(
            'https-value-best-practice', sets={'best-practice'}
        ),
    ]


class HttpsRecord(ValuesMixin, Record):
    REFERENCES: tuple[str, ...] = (
        'https://datatracker.ietf.org/doc/html/rfc9460',
        'https://datatracker.ietf.org/doc/html/rfc9461',
        'https://datatracker.ietf.org/doc/html/rfc9462',
    )
    _type = 'HTTPS'  # type: ignore[misc]
    _value_type = HttpsValue  # type: ignore[misc]


Record.register_type(HttpsRecord)
