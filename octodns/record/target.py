#
#
#

from fqdn import FQDN

from ..idna import idna_encode
from .validator import ValueValidator


def validate_target_fqdn(target, _type, key='value'):
    if not target:
        return [f'missing {key}']

    # Allow null target for records types that support it.
    if target == '.' and _type in ['HTTPS', 'MX', 'SVCB', 'SRV']:
        return []

    # Bypass record value validation if it contains templating variables as they
    # haven't been substituted yet.
    if '{' in target and '}' in target:
        return []

    reasons = []
    target = idna_encode(target)
    if not FQDN(str(target), allow_underscores=True).is_valid:
        reasons.append(f'{_type} {key} "{target}" is not a valid FQDN')

    if not target.endswith('.'):
        reasons.append(f'{_type} {key} "{target}" missing trailing .')

    return reasons


class TargetValueValidator(ValueValidator):
    @classmethod
    def validate(cls, value_cls, data, _type):
        return validate_target_fqdn(data, _type)


class TargetsValueValidator(ValueValidator):
    @classmethod
    def validate(cls, value_cls, data, _type):
        if not data:
            return ['missing value(s)']

        reasons = []
        for value in data:
            reasons += validate_target_fqdn(value, _type)

        return reasons


class _TargetValue(str):
    VALIDATORS = [TargetValueValidator]

    @classmethod
    def parse_rdata_text(self, value):
        return value

    @classmethod
    def _schema(cls):
        return {'type': 'string'}

    @classmethod
    def validate(cls, data, _type):
        reasons = []
        for validator in _TargetValue.VALIDATORS:
            reasons.extend(validator.validate(cls, data, _type))
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

    def template(self, params):
        if '{' not in self:
            return self
        return self.__class__(self.format(**params))


#
# much like _TargetValue, but geared towards multiple values
class _TargetsValue(str):
    VALIDATORS = [TargetsValueValidator]

    @classmethod
    def parse_rdata_text(cls, value):
        return value

    @classmethod
    def _schema(cls):
        return {'type': 'string'}

    @classmethod
    def validate(cls, data, _type):
        reasons = []
        for validator in _TargetsValue.VALIDATORS:
            reasons.extend(validator.validate(cls, data, _type))
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

    def template(self, params):
        if '{' not in self:
            return self
        return self.__class__(self.format(**params))
