from __future__ import annotations

from typing import Any, Iterable

from ..zone import Zone
from .base import BaseProcessor


def _no_trailing_dot(record: Any, prop: str) -> bool:
    return any(getattr(v, prop)[-1] != '.' for v in record.values)  # type: ignore[attr-defined]


def _ensure_trailing_dots(record: Any, prop: str) -> Any:
    new = record.copy()
    for value in new.values:
        val = getattr(value, prop)
        if val[-1] != '.':
            # these will generally be str, but just in case we'll use the
            # constructor
            setattr(value, prop, val.__class__(f'{val}.'))
    return new


class EnsureTrailingDots(BaseProcessor):
    def process_source_zone(
        self, desired: Zone, sources: Iterable[Any], lenient: bool = False
    ) -> Zone:
        lenient = self.lenient or lenient
        for record in desired.records:
            _type = record._type  # type: ignore[attr-defined]
            if _type in ('ALIAS', 'CNAME', 'DNAME') and record.value[-1] != '.':  # type: ignore[attr-defined]
                new = record.copy()
                # we need to preserve the value type (class) here and there's no
                # way to change a strings value, these all inherit from string,
                # so we need to create a new one of the same type
                new.value = new.value.__class__(f'{new.value}.')
                desired.add_record(new, replace=True, lenient=lenient)
            elif _type in ('NS', 'PTR') and any(  # type: ignore[attr-defined]
                v[-1] != '.' for v in record.values
            ):
                new = record.copy()
                klass = new.values[0].__class__
                new.values = [  # type: ignore[attr-defined]
                    v if v[-1] == '.' else klass(f'{v}.') for v in record.values
                ]
                desired.add_record(new, replace=True, lenient=lenient)
            elif _type == 'MX' and _no_trailing_dot(record, 'exchange'):  # type: ignore[attr-defined]
                new = _ensure_trailing_dots(record, 'exchange')
                desired.add_record(new, replace=True, lenient=lenient)
            elif _type == 'SRV' and _no_trailing_dot(record, 'target'):  # type: ignore[attr-defined]
                new = _ensure_trailing_dots(record, 'target')
                desired.add_record(new, replace=True, lenient=lenient)

        return desired
