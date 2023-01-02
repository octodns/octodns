#
#
#

from fqdn import FQDN

from ..idna import idna_encode
from .base import Record, ValueMixin, ValuesMixin
from .dynamic import _DynamicMixin


class _TargetValue(str):
    @classmethod
    def parse_rdata_text(self, value):
        return value

    @classmethod
    def validate(cls, data, _type):
        reasons = []
        if data == '':
            reasons.append('empty value')
        elif not data:
            reasons.append('missing value')
        else:
            data = idna_encode(data)
            if not FQDN(str(data), allow_underscores=True).is_valid:
                reasons.append(f'{_type} value "{data}" is not a valid FQDN')
            elif not data.endswith('.'):
                reasons.append(f'{_type} value "{data}" missing trailing .')
        return reasons

    @classmethod
    def process(cls, value):
        if value:
            return cls(value)
        return None

    def __new__(cls, v):
        v = idna_encode(v)
        return super().__new__(cls, v)

    @property
    def rdata_text(self):
        return self


#
# much like _TargetValue, but geared towards multiple values
class _TargetsValue(str):
    @classmethod
    def parse_rdata_text(cls, value):
        return value

    @classmethod
    def validate(cls, data, _type):
        if not data:
            return ['missing value(s)']
        elif not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            value = idna_encode(value)
            if not FQDN(value, allow_underscores=True).is_valid:
                reasons.append(
                    f'Invalid {_type} value "{value}" is not a valid FQDN.'
                )
            elif not value.endswith('.'):
                reasons.append(f'{_type} value "{value}" missing trailing .')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __new__(cls, v):
        v = idna_encode(v)
        return super().__new__(cls, v)

    @property
    def rdata_text(self):
        return self


class AliasValue(_TargetValue):
    pass


class AliasRecord(ValueMixin, Record):
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


class DnameValue(_TargetValue):
    pass


class DnameRecord(_DynamicMixin, ValueMixin, Record):
    _type = 'DNAME'
    _value_type = DnameValue


Record.register_type(DnameRecord)


class NsValue(_TargetsValue):
    pass


class NsRecord(ValuesMixin, Record):
    _type = 'NS'
    _value_type = NsValue


Record.register_type(NsRecord)


class PtrValue(_TargetsValue):
    pass


class PtrRecord(ValuesMixin, Record):
    _type = 'PTR'
    _value_type = PtrValue

    # This is for backward compatibility with providers that don't support
    # multi-value PTR records.
    @property
    def value(self):
        return self.values[0]


Record.register_type(PtrRecord)
