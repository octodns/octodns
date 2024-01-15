#
#
#

from .base import Record, ValuesMixin, readonly
from .target import _TargetsValue


class NsValue(_TargetsValue):
    pass


class NsRecord(ValuesMixin, Record):
    _type = readonly('NS')
    _value_type = NsValue


Record.register_type(NsRecord)
