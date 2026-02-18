#
#
#

from fqdn import FQDN

from ..idna import idna_encode


def validate_target_fqdn(target, _type):
    # YAML kay name for target.
    key = 'value'
    if _type == 'MX':
        key = 'exchange'
    elif _type in ['HTTPS', 'SVCB']:
        key = 'targetname'
    elif _type == 'SRV':
        key = 'target'

    if not target:
        return [f'missing {key}']

    # Allow null target for records types that support it.
    if target == '.' and _type in ['HTTPS', 'MX', 'SVCB', 'SRV']:
        return []

    # Bypass record value validation if it contains templating variables as they
    # haven't been substituted yet.
    if '{' and '}' in target:
        return []

    reasons = []
    target = idna_encode(target)
    if not FQDN(str(target), allow_underscores=True).is_valid:
        reasons.append(f'{_type} {key} "{target}" is not a valid FQDN')

    if not target.endswith('.'):
        reasons.append(f'{_type} {key} "{target}" missing trailing .')

    return reasons


class _TargetValue(str):
    @classmethod
    def parse_rdata_text(self, value):
        return value

    @classmethod
    def validate(cls, data, _type):
        return validate_target_fqdn(data, _type)

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
    @classmethod
    def parse_rdata_text(cls, value):
        return value

    @classmethod
    def validate(cls, data, _type):
        if not data:
            return ['missing value(s)']

        reasons = []
        for value in data:
            reasons += validate_target_fqdn(value, _type)

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
