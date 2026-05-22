#
#
#

from typing import ClassVar, Type

from .base import Record, ValueMixin
from .dynamic import _DynamicMixin
from .target import _TargetValue


class DnameValue(_TargetValue):
    pass


class DnameRecord(_DynamicMixin, ValueMixin, Record):
    REFERENCES: tuple[str, ...] = (
        'https://datatracker.ietf.org/doc/html/rfc6672',
    )
    _type: ClassVar[str] = 'DNAME'
    _value_type: ClassVar[Type[DnameValue]] = DnameValue  # type: ignore[misc]


Record.register_type(DnameRecord)
