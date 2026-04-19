#
#
#

from .base import Record, ValueMixin
from .target import _TargetValue


class AliasValue(_TargetValue):
    pass


class AliasRecord(ValueMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/draft-ietf-dnsop-aname/',)
    _type = 'ALIAS'
    _value_type = AliasValue

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = []
        if name != '':
            reasons.append('non-root ALIAS not allowed')
        reasons.extend(super().validate(name, fqdn, data))
        return reasons


Record.register_type(AliasRecord)
