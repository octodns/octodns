#
#
#

from .base import Record, ValueMixin
from .target import _TargetValue
from .validator import RecordValidator


class AliasValue(_TargetValue):
    pass


class AliasRootValidator(RecordValidator):
    '''
    Restricts ALIAS records to the zone root — the non-standard ALIAS
    type only has meaning at the apex.
    '''

    def validate(self, record_cls, name, fqdn, data):
        if name != '':
            return ['non-root ALIAS not allowed']
        return []


class AliasRecord(ValueMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/draft-ietf-dnsop-aname/',)
    _type = 'ALIAS'
    _value_type = AliasValue


Record.register_type(AliasRecord)
Record.register_validator(AliasRootValidator('alias-root'), types=['ALIAS'])
Record.register_validator(_TargetValue.VALIDATOR, types=['ALIAS'])
