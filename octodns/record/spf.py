#
#
#
#

from __future__ import annotations

from typing import Any

from ..deprecation import deprecated
from .base import Record
from .chunked import _ChunkedValue, _ChunkedValuesMixin


class SpfRecord(_ChunkedValuesMixin, Record):
    REFERENCES: tuple[str, ...] = (
        'https://datatracker.ietf.org/doc/html/rfc7208',
    )
    _type = 'SPF'  # type: ignore[misc]
    _value_type = _ChunkedValue  # type: ignore[misc]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        deprecated(
            'The SPF record type is DEPRECATED in favor of TXT values and will become an ValidationError in 2.0',
            stacklevel=99,
        )


Record.register_type(SpfRecord)
