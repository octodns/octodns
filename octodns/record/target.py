#
#
#

from fqdn import FQDN

from ..idna import idna_encode


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
        if not data or all(not d for d in data):
            return ['missing value(s)']
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
