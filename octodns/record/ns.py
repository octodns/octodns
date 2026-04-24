#
#
#

from .base import Record, ValuesMixin
from .target import TargetsValueValidator, _TargetsValue


class NsValue(_TargetsValue):
    pass


class NsRecord(ValuesMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc1035',)
    _type = 'NS'
    _value_type = NsValue


Record.register_type(NsRecord)
Record.register_validator(TargetsValueValidator('targets-value'), types=['NS'])
