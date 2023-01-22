#
#
#

from .base import Record, ValuesMixin
from .target import _TargetsValue


class NsValue(_TargetsValue):
    pass


class NsRecord(ValuesMixin, Record):
    _type = 'NS'
    _value_type = NsValue


Record.register_type(NsRecord)
