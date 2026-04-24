#
#
#

from .base import Record, ValueMixin
from .dynamic import _DynamicMixin
from .target import _TargetValue


class DnameValue(_TargetValue):
    pass


class DnameRecord(_DynamicMixin, ValueMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc6672',)
    _type = 'DNAME'
    _value_type = DnameValue


Record.register_type(DnameRecord)
Record.register_validator(_DynamicMixin.VALIDATOR, types=['DNAME'])
Record.register_validator(_TargetValue.VALIDATOR, types=['DNAME'])
