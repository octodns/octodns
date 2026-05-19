#
#
#
#

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base import Record, ValuesMixin
from .validator import ValueValidator

if TYPE_CHECKING:
    from typing import Iterable


class OpenpgpkeyValueValidator(ValueValidator):
    '''
    Validates OPENPGPKEY values: at least one non-empty base64-encoded
    OpenPGP key must be provided.
    '''

    def validate(
        self, value_cls: Any, data: Iterable[dict[str, Any]], _type: str
    ) -> list[str]:
        if not data or all(not d for d in data):
            return ['missing value(s)']
        return []


class OpenpgpkeyValue(str):
    '''
    OPENPGPKEY value - base64-encoded OpenPGP public key

    RFC 7929 - DANE Bindings for OpenPGP
    '''

    VALIDATORS: list[Any] = [
        OpenpgpkeyValueValidator(
            'openpgpkey-value-rfc', sets={'legacy', 'strict'}
        )
    ]

    @classmethod
    def _schema(cls) -> dict[str, Any]:
        return {'type': 'string'}

    @classmethod
    def parse_rdata_text(cls, value: str) -> str:
        # Strip whitespace that may appear in zone files (base64 data may be
        # split across lines)
        return value.replace(' ', '')

    @classmethod
    def process(cls, values: Iterable[str]) -> list[OpenpgpkeyValue]:
        return [cls(v) for v in values]

    @property
    def rdata_text(self) -> str:
        return self

    def template(self, params: dict[str, Any]) -> OpenpgpkeyValue:
        if '{' not in self:
            return self
        return self.__class__(self.format(**params))


class OpenpgpkeyRecord(ValuesMixin, Record):
    REFERENCES: tuple[str, ...] = (
        'https://datatracker.ietf.org/doc/html/rfc7929',
    )
    _type = 'OPENPGPKEY'  # type: ignore[misc]
    _value_type = OpenpgpkeyValue  # type: ignore[misc]


Record.register_type(OpenpgpkeyRecord)
