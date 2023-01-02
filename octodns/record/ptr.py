#
#
#

from .base import Record, ValuesMixin
from .target import _TargetsValue


class PtrValue(_TargetsValue):
    pass


class PtrRecord(ValuesMixin, Record):
    _type = 'PTR'
    _value_type = PtrValue

    # This is for backward compatibility with providers that don't support
    # multi-value PTR records.
    @property
    def value(self):
        return self.values[0]


Record.register_type(PtrRecord)
