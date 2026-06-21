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
    '''
    Rejects CNAME records at the zone root, which are prohibited by
    RFC 1034/2181.
    '''

    def validate(self, record_cls, name, fqdn, data):
        if name == '':
            return ['root CNAME not allowed']
        return []


class CnameRecord(_DynamicMixin, ValueMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc1035',)
    _type = 'CNAME'
    _value_type = CnameValue
    VALIDATORS = [
        CnameRootValidator('cname-root-rfc', sets={'legacy', 'strict'})
    ]


Record.register_type(CnameRecord)
