#
#
#

from fqdn import FQDN

from ..idna import idna_encode
from .validator import ValueValidator


def _check_target_format(target, _type, key='value'):
    if not target:
        return [f'missing {key}']
    if target == '.' and _type in ['HTTPS', 'MX', 'SVCB', 'SRV']:
        return []
    if '{' in target and '}' in target:
        return []
    target = idna_encode(target)
    if not FQDN(str(target), allow_underscores=True).is_valid:
        return [f'{_type} {key} "{target}" is not a valid FQDN']
    return []


def _check_target_trailing_dot(target, _type, key='value'):
    if not target:
        return []
    if target == '.' and _type in ['HTTPS', 'MX', 'SVCB', 'SRV']:
        return []
    if '{' in target and '}' in target:
        return []
    target = idna_encode(target)
    if not target.endswith('.'):
        return [f'{_type} {key} "{target}" missing trailing .']
    return []


def validate_target_fqdn(target, _type, key='value'):
    return _check_target_format(
        target, _type, key
    ) + _check_target_trailing_dot(target, _type, key)


class TargetValueValidator(ValueValidator):
    '''
    Validates a single-value target FQDN (CNAME, ALIAS, DNAME, PTR).
    '''

    def validate(self, value_cls, data, _type):
        return _check_target_format(data, _type)


class TargetsValueValidator(ValueValidator):
    '''
    Validates a list of target FQDNs (NS). Rejects empty lists.
    '''

    def validate(self, value_cls, data, _type):
        if not data:
            return ['missing value(s)']

        reasons = []
        for value in data:
            reasons += _check_target_format(value, _type)

        return reasons


class TargetValueBestPracticeValidator(ValueValidator):
    '''
    Checks that a single-value target ends with a trailing ``.`` (i.e. is
    an absolute/fully-qualified name).  Without the trailing dot, resolvers
    may append the host's search domain, multiplying query traffic.

    Enabled as part of the ``best-practice`` validator set::

      manager:
        enabled:
          - best-practice
    '''

    def validate(self, value_cls, data, _type):
        return _check_target_trailing_dot(data, _type)


class TargetsValueBestPracticeValidator(ValueValidator):
    '''
    Checks that each target in a multi-value record ends with a trailing
    ``.`` (i.e. is an absolute/fully-qualified name).

    Enabled as part of the ``best-practice`` validator set::

      manager:
        enabled:
          - best-practice
    '''

    def validate(self, value_cls, data, _type):
        reasons = []
        for value in data:
            reasons += _check_target_trailing_dot(value, _type)
        return reasons


class _TargetValue(str):
    VALIDATORS = [
        TargetValueValidator('target-value-rfc', sets={'legacy', 'strict'}),
        TargetValueBestPracticeValidator(
            'target-value-best-practice', sets={'best-practice'}
        ),
    ]

    @classmethod
    def parse_rdata_text(self, value):
        return value

    @classmethod
    def _schema(cls):
        return {'type': 'string'}

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
    VALIDATORS = [
        TargetsValueValidator('targets-value-rfc', sets={'legacy', 'strict'}),
        TargetsValueBestPracticeValidator(
            'targets-value-best-practice', sets={'best-practice'}
        ),
    ]

    @classmethod
    def parse_rdata_text(cls, value):
        return value

    @classmethod
    def _schema(cls):
        return {'type': 'string'}

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
