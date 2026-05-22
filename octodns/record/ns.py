#
#
#

from typing import ClassVar, Type

from .base import Record, ValuesMixin
from .target import _TargetsValue


class NsValue(_TargetsValue):
    pass


class NsRecord(ValuesMixin, Record):
    REFERENCES: tuple[str, ...] = (
        'https://datatracker.ietf.org/doc/html/rfc1035',
    )
    _type: ClassVar[str] = 'NS'
    _value_type: ClassVar[Type[NsValue]] = NsValue  # type: ignore[misc]


Record.register_type(NsRecord)
