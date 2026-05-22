#
#
#
#

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from .base import ValuesMixin
from .validator import ValueValidator

if TYPE_CHECKING:
    from typing import Iterable, Sequence


class ChunkedValueValidator(ValueValidator):
    '''
    Validates values for TXT/SPF-style chunked strings: present,
    ASCII-only, with no unescaped or double-escaped ``;`` characters.
    '''

    _unescaped_semicolon_re = re.compile(r'\w;')
    _double_escaped_semicolon_re = re.compile(r'\\\\;')

    def validate(
        self,
        value_cls: Any,
        data: Iterable[dict[str, Any]] | Sequence[Any] | str,
        _type: str,
    ) -> list[str]:
        if not data:
            return ['missing value(s)']
        elif not isinstance(data, (list, tuple)):
            data = (data,)
        reasons: list[str] = []
        for value in data:  # type: ignore[assignment]
            if value is None:
                reasons.append('missing value(s)')
                continue
            if self._unescaped_semicolon_re.search(value):
                reasons.append(f'unescaped ; in "{value}"')
            if self._double_escaped_semicolon_re.search(value):
                reasons.append(f'double escaped ; in "{value}"')
            try:
                value.encode('ascii')
            except UnicodeEncodeError:
                reasons.append(f'non ASCII character in "{value}"')
        return reasons


chunked_value_validator = ChunkedValueValidator(
    'chunked-value-rfc', sets={'legacy', 'strict'}
)


class _ChunkedValuesMixin(ValuesMixin):
    CHUNK_SIZE = 255

    def chunked_value(self, value: str) -> Any:
        value = value.replace('"', '\\"')
        vs: list[str] = []
        i = 0
        n = len(value)
        # until we've processed the whole string
        while i < n:
            # start with a full chunk size
            c = min(self.CHUNK_SIZE, n - i)
            # make sure that we don't break on escape chars
            while value[i + c - 1] == '\\':
                c -= 1
            # we have our chunk now
            vs.append(value[i : i + c])
            # and can step over if
            i += c
        vs_str = '" "'.join(vs)
        return self._value_type(f'"{vs_str}"')  # type: ignore[attr-defined]

    @property
    def chunked_values(self) -> list[Any]:
        values = []
        for v in self.values:  # type: ignore[attr-defined]
            values.append(self.chunked_value(v))
        return values

    @property
    def rr_values(self) -> list[Any]:
        return self.chunked_values


class _ChunkedValue(str):
    VALIDATORS = [chunked_value_validator]

    @classmethod
    def parse_rdata_text(cls, value: Any) -> str | Any:
        try:
            return value.replace(';', '\\;')
        except AttributeError:
            return value

    @classmethod
    def _schema(cls) -> dict[str, Any]:
        return {'type': 'string'}

    @classmethod
    def process(cls, values: Iterable[Any]) -> list[_ChunkedValue]:
        ret = []
        for v in values:
            if v and v[0] == '"':
                v = v[1:-1]
            ret.append(cls(v.replace('" "', '')))
        return ret

    @property
    def rdata_text(self) -> str:
        return self

    def template(self, params: dict[str, Any]) -> _ChunkedValue:
        if '{' not in self:
            return self
        return self.__class__(self.format(**params))
