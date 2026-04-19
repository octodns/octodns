#
#
#

from .base import Record, ValueMixin
from .dynamic import _DynamicMixin
from .target import _TargetValue
from .validator import RecordValidator


class CnameValue(_TargetValue):
    pass


class CnameRootValidator(RecordValidator):
    @classmethod
    def validate(cls, record_cls, name, fqdn, data):
        if name == '':
            return ['root CNAME not allowed']
        return []


class CnameRecord(_DynamicMixin, ValueMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc1035',)
    _type = 'CNAME'
    _value_type = CnameValue

    VALIDATORS = [CnameRootValidator]

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = []
        for validator in CnameRecord.VALIDATORS:
            reasons.extend(validator.validate(cls, name, fqdn, data))
        reasons.extend(super().validate(name, fqdn, data))
        return reasons


Record.register_type(CnameRecord)
