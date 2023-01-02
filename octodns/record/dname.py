#
#
#

from .base import Record, ValueMixin
from .dynamic import _DynamicMixin
from .target import _TargetValue


class DnameValue(_TargetValue):
    pass


class DnameRecord(_DynamicMixin, ValueMixin, Record):
    _type = 'DNAME'
    _value_type = DnameValue


Record.register_type(DnameRecord)
