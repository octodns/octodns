#
#
#

from typing import Optional, Sequence

from fqdn import FQDN

from ..idna import idna_encode
from .validator import ValueValidator


def _check_target_format(
    target: str, _type: str, key: str = 'value'
) -> list[str]:
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


def _check_target_trailing_dot(
    target: str, _type: str, key: str = 'value'
) -> list[str]:
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


class TargetValueValidator(ValueValidator):
    '''
    Validates a single-value target FQDN (CNAME, ALIAS, DNAME, PTR).
    '''

    def validate(
        self, value_cls: type, data: Optional[str], _type: str
    ) -> list[str]:
        return _check_target_format(data or '', _type)


class TargetsValueValidator(ValueValidator):
    '''
    Validates a list of target FQDNs (NS). Rejects empty lists.
    '''

    def validate(
        self, value_cls: type, data: Sequence[Optional[str]], _type: str
    ) -> list[str]:
        if not data:
            return ['missing value(s)']

        reasons: list[str] = []
        for value in data:
            reasons += _check_target_format(value or '', _type)

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

    def validate(
        self, value_cls: type, data: Optional[str], _type: str
    ) -> list[str]:
        return _check_target_trailing_dot(data or '', _type)


class TargetsValueBestPracticeValidator(ValueValidator):
    '''
    Checks that each target in a multi-value record ends with a trailing
    ``.`` (i.e. is an absolute/fully-qualified name).

    Enabled as part of the ``best-practice`` validator set::

      manager:
        enabled:
          - best-practice
    '''

    def validate(
        self, value_cls: type, data: Sequence[Optional[str]], _type: str
    ) -> list[str]:
        reasons: list[str] = []
        for value in data:
            reasons += _check_target_trailing_dot(value or '', _type)
        return reasons


class _TargetValue(str):
    VALIDATORS: list[ValueValidator] = [
        TargetValueValidator('target-value-rfc', sets={'legacy', 'strict'}),
        TargetValueBestPracticeValidator(
            'target-value-best-practice', sets={'best-practice'}
        ),
    ]

    @classmethod
    def parse_rdata_text(cls, value: str) -> str:
        return value

    @classmethod
    def _schema(cls) -> dict[str, str]:
        return {'type': 'string'}

    @classmethod
    def process(cls, value: Optional[str]) -> Optional['_TargetValue']:
        if value:
            return cls(value)
        return None

    def __new__(cls, v: str) -> '_TargetValue':
        v = idna_encode(v)
        return super().__new__(cls, v)  # type: ignore[call-arg]

    @property
    def rdata_text(self) -> str:
        return self

    def template(self, params: dict[str, object]) -> '_TargetValue':
        if '{' not in self:
            return self
        return self.__class__(self.format(**params))  # type: ignore[return-value]


#
# much like _TargetValue, but geared towards multiple values
class _TargetsValue(str):
    VALIDATORS: list[ValueValidator] = [
        TargetsValueValidator('targets-value-rfc', sets={'legacy', 'strict'}),
        TargetsValueBestPracticeValidator(
            'targets-value-best-practice', sets={'best-practice'}
        ),
    ]

    @classmethod
    def parse_rdata_text(cls, value: str) -> str:
        return value

    @classmethod
    def _schema(cls) -> dict[str, str]:
        return {'type': 'string'}

    @classmethod
    def process(cls, values: Sequence[Optional[str]]) -> list['_TargetsValue']:
        return [cls(v or '') for v in values]

    def __new__(cls, v: str) -> '_TargetsValue':
        v = idna_encode(v)
        return super().__new__(cls, v)  # type: ignore[call-arg]

    @property
    def rdata_text(self) -> str:
        return self

    def template(self, params: dict[str, object]) -> '_TargetsValue':
        if '{' not in self:
            return self
        return self.__class__(self.format(**params))  # type: ignore[return-value]
