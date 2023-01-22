#
#
#

from .base import Record, ValueMixin
from .dynamic import _DynamicMixin
from .target import _TargetValue


class CnameValue(_TargetValue):
    pass


class CnameRecord(_DynamicMixin, ValueMixin, Record):
    _type = 'CNAME'
    _value_type = CnameValue

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = []
        if name == '':
            reasons.append('root CNAME not allowed')
        reasons.extend(super().validate(name, fqdn, data))
        return reasons


Record.register_type(CnameRecord)
