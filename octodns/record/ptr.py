#
#
#

from .base import Record, ValuesMixin
from .target import _TargetsValue


class PtrValue(_TargetsValue):
    pass


class PtrRecord(ValuesMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc1035',)
    _type = 'PTR'
    _value_type = PtrValue

    # This is for backward compatibility with providers that don't support
    # multi-value PTR records.
    @property
    def value(self):
        return self.values[0]


Record.register_type(PtrRecord)
Record.register_validator(_TargetsValue.VALIDATOR, types=['PTR'])
