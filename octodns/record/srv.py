#
#
#
#

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from ..equality import EqualityTupleMixin
from ..idna import idna_encode
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError
from .target import _check_target_format, _check_target_trailing_dot
from .validator import RecordValidator, ValueValidator

if TYPE_CHECKING:
    from typing import Iterable


class SrvNameValidator(RecordValidator):
    '''
    Validates that an SRV record's name matches the
    ``_service._protocol`` pattern required by RFC 2782 (e.g.
    ``_http._tcp``), or is a wildcard.
    '''

    _name_re = re.compile(r'^(\*|_[^\.]+)\.[^\.]+')

    def validate(
        self, record_cls: Any, name: str, fqdn: str, data: Any
    ) -> list[str]:
        if not self._name_re.match(name):
            return ['invalid name for SRV record']
        return []


class SrvValueValidator(ValueValidator):
    '''
    Validates SRV rdata: priority, weight, and port are present and
    integer-parsable, and target is a valid FQDN.
    '''

    def validate(self, value_cls: Any, data: Any, _type: str) -> list[str]:
        reasons: list[str] = []
        for value in data:
            try:
                int(value['priority'])
            except KeyError:
                reasons.append('missing priority')
            except ValueError:
                reasons.append(f'invalid priority "{value["priority"]}"')
            try:
                int(value['weight'])
            except KeyError:
                reasons.append('missing weight')
            except ValueError:
                reasons.append(f'invalid weight "{value["weight"]}"')
            try:
                int(value['port'])
            except KeyError:
                reasons.append('missing port')
            except ValueError:
                reasons.append(f'invalid port "{value["port"]}"')
            try:
                target = value['target']
                reasons += _check_target_format(target, _type, 'target')
            except KeyError:
                reasons.append('missing target')
        return reasons


class SrvNameRfcValidator(RecordValidator):
    '''
    Strict SRV name validator per RFC 2782 and RFC 6335 §5.1.

    Requires the first two labels of the record name to be
    ``_service._proto`` (``*._proto`` is still accepted for wildcards).
    Both the service and proto label bodies (after the leading ``_``)
    must conform to the RFC 6335 §5.1 service name syntax: 1-15
    characters, starting with a letter, ending with a letter or digit,
    containing only letters, digits, and hyphens, and with no
    consecutive hyphens.

    Enabled as part of the ``rfc`` validator set::

      manager:
        enabled:
          - rfc
    '''

    _max_len = 15

    @classmethod
    def _is_valid_service_name(cls, body: str) -> bool:
        if not body or len(body) > cls._max_len:
            return False
        if not body[0].isalpha():
            return False
        if not body[-1].isalnum():
            return False
        if '--' in body:
            return False
        return all(c.isalnum() or c == '-' for c in body)

    def validate(
        self, record_cls: Any, name: str, fqdn: str, data: Any
    ) -> list[str]:
        labels = name.split('.') if name else []
        if len(labels) < 2:
            return ['SRV name must have at least two labels (_service._proto)']

        reasons: list[str] = []
        service, proto = labels[0], labels[1]
        if service != '*' and not (
            service.startswith('_') and self._is_valid_service_name(service[1:])
        ):
            reasons.append(f'invalid SRV service label "{service}"')
        if not (
            proto.startswith('_') and self._is_valid_service_name(proto[1:])
        ):
            reasons.append(f'invalid SRV proto label "{proto}"')
        return reasons


class SrvValueRfcValidator(ValueValidator):
    '''
    Strict SRV rdata validator per RFC 2782.

    - ``priority``, ``weight``, and ``port`` must each be in the
      0-65535 range.
    - When ``target`` is ``"."``, ``priority``, ``weight``, and
      ``port`` must all be ``0`` (RFC 2782 "service not available"
      convention).
    - When ``target`` is not ``"."``, ``port`` must be greater than
      0 (port 0 is IANA-reserved).

    Assumes the base ``SrvValueValidator`` has already caught missing
    or non-integer fields; entries that fail those checks are skipped
    here to avoid duplicated reasons. Enabled as part of the ``rfc``
    set::

      manager:
        enabled:
          - rfc
    '''

    @staticmethod
    def _as_int(value: dict[str, Any], field: str) -> int | None:
        try:
            return int(value[field])
        except (KeyError, ValueError, TypeError):
            return None

    def validate(self, value_cls: Any, data: Any, _type: str) -> list[str]:
        reasons: list[str] = []
        for value in data:
            fields = {
                name: self._as_int(value, name)
                for name in ('priority', 'weight', 'port')
            }
            for name, v in fields.items():
                if v is not None and not 0 <= v <= 65535:
                    reasons.append(f'{name} "{v}" out of range 0-65535')
            target = value.get('target')
            if target == '.':
                for name, v in fields.items():
                    if v is not None and v != 0:
                        reasons.append(f'{name} must be 0 when target is "."')
            elif target and fields['port'] == 0:
                reasons.append(
                    'port 0 is reserved; must be > 0 when target is not "."'
                )
        return reasons


class SrvValueBestPracticeValidator(ValueValidator):
    '''
    Checks that the SRV ``target`` field ends with a trailing ``.``
    (fully-qualified name).

    Enabled as part of the ``best-practice`` validator set::

      manager:
        enabled:
          - best-practice
    '''

    def validate(self, value_cls: Any, data: Any, _type: str) -> list[str]:
        reasons: list[str] = []
        for value in data:
            target = value.get('target')
            if target:
                reasons += _check_target_trailing_dot(target, _type, 'target')
        return reasons


class SrvValue(EqualityTupleMixin, dict):
    VALIDATORS: list[Any] = [
        SrvValueValidator('srv-value', sets={'legacy'}),
        SrvValueRfcValidator('srv-value-rfc', sets={'strict'}),
        SrvValueBestPracticeValidator(
            'srv-value-best-practice', sets={'best-practice'}
        ),
    ]

    @classmethod
    def _schema(cls) -> dict[str, Any]:
        return {
            'type': 'object',
            'required': ['priority', 'weight', 'port', 'target'],
            'properties': {
                'priority': {'type': 'integer', 'minimum': 0, 'maximum': 65535},
                'weight': {'type': 'integer', 'minimum': 0, 'maximum': 65535},
                'port': {'type': 'integer', 'minimum': 0, 'maximum': 65535},
                'target': {'type': 'string'},
            },
        }

    @classmethod
    def parse_rdata_text(cls, value: str) -> dict[str, Any]:
        try:
            priority, weight, port, target = value.split(' ')
        except ValueError:
            raise RrParseError()
        parsed_priority: int | str = priority
        try:
            parsed_priority = int(priority)
        except ValueError:
            pass
        parsed_weight: int | str = weight
        try:
            parsed_weight = int(weight)
        except ValueError:
            pass
        parsed_port: int | str = port
        try:
            parsed_port = int(port)
        except ValueError:
            pass
        parsed_target: str = unquote(target)  # type: ignore[assignment]
        return {
            'priority': parsed_priority,
            'weight': parsed_weight,
            'port': parsed_port,
            'target': parsed_target,
        }

    @classmethod
    def process(cls, values: Iterable[dict[str, Any]]) -> list[SrvValue]:
        return [cls(v) for v in values]

    def __init__(self, value: dict[str, Any]) -> None:
        super().__init__(
            {
                'priority': int(value['priority']),
                'weight': int(value['weight']),
                'port': int(value['port']),
                'target': idna_encode(value['target']),
            }
        )

    @property
    def priority(self) -> int:
        return self['priority']  # type: ignore[no-any-return]

    @priority.setter
    def priority(self, value: int) -> None:
        self['priority'] = value

    @property
    def weight(self) -> int:
        return self['weight']  # type: ignore[no-any-return]

    @weight.setter
    def weight(self, value: int) -> None:
        self['weight'] = value

    @property
    def port(self) -> int:
        return self['port']  # type: ignore[no-any-return]

    @port.setter
    def port(self, value: int) -> None:
        self['port'] = value

    @property
    def target(self) -> str:
        return self['target']  # type: ignore[no-any-return]

    @target.setter
    def target(self, value: str) -> None:
        self['target'] = value

    @property
    def data(self) -> dict[str, Any]:
        return self  # type: ignore[return-value]

    @property
    def rdata_text(self) -> str:
        return f"{self.priority} {self.weight} {self.port} {self.target}"

    def template(self, params: dict[str, Any]) -> SrvValue | None:
        if '{' not in self.target:
            return self
        new = self.__class__(self)
        new.target = new.target.format(**params)
        return new

    def __hash__(self) -> int:  # type: ignore[override]
        return hash(self.__repr__())

    def _equality_tuple(self) -> tuple[int, int, int, str]:
        return (self.priority, self.weight, self.port, self.target)

    def __repr__(self) -> str:
        return f"'{self.priority} {self.weight} {self.port} {self.target}'"


class SrvRecord(ValuesMixin, Record):
    REFERENCES: tuple[str, ...] = (
        'https://datatracker.ietf.org/doc/html/rfc2782',
        'https://datatracker.ietf.org/doc/html/rfc6335',
    )
    _type = 'SRV'  # type: ignore[misc]
    _value_type = SrvValue  # type: ignore[misc]
    VALIDATORS: list[Any] = [
        SrvNameValidator('srv-name', sets={'legacy'}),
        SrvNameRfcValidator('srv-name-rfc', sets={'strict'}),
    ]


Record.register_type(SrvRecord)
