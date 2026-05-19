#
#
#

from typing import ClassVar, Type

from .base import Record, ValuesMixin
from .target import _TargetsValue


class PtrValue(_TargetsValue):
    pass


class PtrRecord(ValuesMixin, Record):
    REFERENCES: tuple[str, ...] = (
        'https://datatracker.ietf.org/doc/html/rfc1035',
    )
    _type: ClassVar[str] = 'PTR'
    _value_type: ClassVar[Type[PtrValue]] = PtrValue  # type: ignore[misc]

    # This is for backward compatibility with providers that don't support
    # multi-value PTR records.
    @property
    def value(self) -> PtrValue:
        return self.values[0]  # type: ignore[index]


Record.register_type(PtrRecord)
