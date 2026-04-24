#
#
#

from .base import Record, ValueMixin
from .dynamic import DynamicValidator, _DynamicMixin
from .target import TargetValueValidator, _TargetValue


class DnameValue(_TargetValue):
    pass


class DnameRecord(_DynamicMixin, ValueMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc6672',)
    _type = 'DNAME'
    _value_type = DnameValue


Record.register_type(DnameRecord)
Record.register_validator(DynamicValidator('dynamic'), types=['DNAME'])
Record.register_validator(TargetValueValidator('target-value'), types=['DNAME'])
