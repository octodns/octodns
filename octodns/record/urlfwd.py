#
#
#
#

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..equality import EqualityTupleMixin
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError
from .validator import ValueValidator

if TYPE_CHECKING:
    from typing import Iterable


class UrlfwdValueValidator(ValueValidator):
    '''
    Validates URLFWD rdata: ``code`` is a valid HTTP redirect code,
    ``masking`` and ``query`` are in the recognized enum sets, and
    ``path`` and ``target`` are present.
    '''

    def validate(self, value_cls: Any, data: Any, _type: str) -> list[str]:
        reasons: list[str] = []
        for value in data:
            try:
                code = int(value['code'])
                if code not in value_cls.VALID_CODES:
                    reasons.append(f'unrecognized return code "{code}"')
            except KeyError:
                reasons.append('missing code')
            except ValueError:
                reasons.append(f'invalid return code "{value["code"]}"')
            try:
                masking = int(value['masking'])
                if masking not in value_cls.VALID_MASKS:
                    reasons.append(f'unrecognized masking setting "{masking}"')
            except KeyError:
                reasons.append('missing masking')
            except ValueError:
                reasons.append(f'invalid masking setting "{value["masking"]}"')
            try:
                query = int(value['query'])
                if query not in value_cls.VALID_QUERY:
                    reasons.append(f'unrecognized query setting "{query}"')
            except KeyError:
                reasons.append('missing query')
            except ValueError:
                reasons.append(f'invalid query setting "{value["query"]}"')
            for k in ('path', 'target'):
                if k not in value:
                    reasons.append(f'missing {k}')
        return reasons


class UrlfwdValue(EqualityTupleMixin, dict):
    VALID_CODES = (301, 302)
    VALID_MASKS = (0, 1, 2)
    VALID_QUERY = (0, 1)

    VALIDATORS: list[Any] = [
        UrlfwdValueValidator('urlfwd-value', sets={'legacy', 'strict'})
    ]

    @classmethod
    def _schema(cls) -> dict[str, Any]:
        return {
            'type': 'object',
            'required': ['path', 'target', 'code', 'masking', 'query'],
            'properties': {
                'path': {'type': 'string'},
                'target': {'type': 'string'},
                'code': {'type': 'integer', 'enum': list(cls.VALID_CODES)},
                'masking': {'type': 'integer', 'enum': list(cls.VALID_MASKS)},
                'query': {'type': 'integer', 'enum': list(cls.VALID_QUERY)},
            },
        }

    @classmethod
    def parse_rdata_text(cls, value: str) -> dict[str, Any]:
        try:
            path, target, code, masking, query = value.split(' ')
        except ValueError:
            raise RrParseError()
        parsed_code: int | str = code
        try:
            parsed_code = int(code)
        except ValueError:
            pass
        parsed_masking: int | str = masking
        try:
            parsed_masking = int(masking)
        except ValueError:
            pass
        parsed_query: int | str = query
        try:
            parsed_query = int(query)
        except ValueError:
            pass
        parsed_path: str = unquote(path)  # type: ignore[assignment]
        parsed_target: str = unquote(target)  # type: ignore[assignment]
        return {
            'path': parsed_path,
            'target': parsed_target,
            'code': parsed_code,
            'masking': parsed_masking,
            'query': parsed_query,
        }

    @classmethod
    def process(cls, values: Iterable[dict[str, Any]]) -> list[UrlfwdValue]:
        return [cls(v) for v in values]

    def __init__(self, value: dict[str, Any]) -> None:
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
    def path(self) -> str:
        return self['path']  # type: ignore[no-any-return]

    @path.setter
    def path(self, value: str) -> None:
        self['path'] = value

    @property
    def target(self) -> str:
        return self['target']  # type: ignore[no-any-return]

    @target.setter
    def target(self, value: str) -> None:
        self['target'] = value

    @property
    def code(self) -> int:
        return self['code']  # type: ignore[no-any-return]

    @code.setter
    def code(self, value: int) -> None:
        self['code'] = value

    @property
    def masking(self) -> int:
        return self['masking']  # type: ignore[no-any-return]

    @masking.setter
    def masking(self, value: int) -> None:
        self['masking'] = value

    @property
    def query(self) -> int:
        return self['query']  # type: ignore[no-any-return]

    @query.setter
    def query(self, value: int) -> None:
        self['query'] = value

    @property
    def rdata_text(self) -> str:
        return f'"{self.path}" "{self.target}" {self.code} {self.masking} {self.query}'

    def template(self, params: dict[str, Any]) -> UrlfwdValue | None:
        if '{' not in self.path and '{' not in self.target:
            return self
        new = self.__class__(self)
        new.path = new.path.format(**params)
        new.target = new.target.format(**params)
        return new

    def _equality_tuple(self) -> tuple[str, str, int, int, int]:
        return (self.path, self.target, self.code, self.masking, self.query)

    def __hash__(self) -> int:  # type: ignore[override]
        return hash(
            (self.path, self.target, self.code, self.masking, self.query)
        )

    def __repr__(self) -> str:
        return f'"{self.path}" "{self.target}" {self.code} {self.masking} {self.query}'


class UrlfwdRecord(ValuesMixin, Record):
    REFERENCES: tuple[str, ...] = ()
    _type = 'URLFWD'  # type: ignore[misc]
    _value_type = UrlfwdValue  # type: ignore[misc]


Record.register_type(UrlfwdRecord)
