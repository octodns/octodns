#
#
#

import re

from ..equality import EqualityTupleMixin
from ..idna import idna_encode
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError
from .target import validate_target_fqdn
from .validator import RecordValidator, ValueValidator


class SrvNameValidator(RecordValidator):
    '''
    Validates that an SRV record's name matches the
    ``_service._protocol`` pattern required by RFC 2782 (e.g.
    ``_http._tcp``), or is a wildcard.
    '''

    _name_re = re.compile(r'^(\*|_[^\.]+)\.[^\.]+')

    @classmethod
    def validate(cls, record_cls, name, fqdn, data):
        if not cls._name_re.match(name):
            return ['invalid name for SRV record']
        return []


class SrvValueValidator(ValueValidator):
    '''
    Validates SRV rdata: priority, weight, and port are present and
    integer-parsable, and target is a valid FQDN.
    '''

    @classmethod
    def validate(cls, value_cls, data, _type):
        reasons = []
        for value in data:
            # TODO: validate algorithm and fingerprint_type values
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
                reasons += validate_target_fqdn(target, _type, 'target')
            except KeyError:
                reasons.append('missing target')
        return reasons


class SrvStrictNameValidator(RecordValidator):
    '''
    Stricter SRV name validator per RFC 2782 and RFC 6335 §5.1.

    Requires the first two labels of the record name to be
    ``_service._proto`` (``*._proto`` is still accepted for wildcards).
    Both the service and proto label bodies (after the leading ``_``)
    must conform to the RFC 6335 §5.1 service name syntax: 1-15
    characters, starting with a letter, ending with a letter or digit,
    containing only letters, digits, and hyphens, and with no
    consecutive hyphens.

    Not enabled by default; opt in by appending to
    ``SrvRecord.VALIDATORS``.
    '''

    _max_len = 15

    @classmethod
    def _is_valid_service_name(cls, body):
        if not body or len(body) > cls._max_len:
            return False
        if not body[0].isalpha():
            return False
        if not body[-1].isalnum():
            return False
        if '--' in body:
            return False
        return all(c.isalnum() or c == '-' for c in body)

    @classmethod
    def validate(cls, record_cls, name, fqdn, data):
        labels = name.split('.') if name else []
        if len(labels) < 2:
            return ['SRV name must have at least two labels (_service._proto)']

        reasons = []
        service, proto = labels[0], labels[1]
        if service != '*' and not (
            service.startswith('_') and cls._is_valid_service_name(service[1:])
        ):
            reasons.append(f'invalid SRV service label "{service}"')
        if not (
            proto.startswith('_') and cls._is_valid_service_name(proto[1:])
        ):
            reasons.append(f'invalid SRV proto label "{proto}"')
        return reasons


class SrvStrictValueValidator(ValueValidator):
    '''
    Stricter SRV rdata validator per RFC 2782.

    - ``priority``, ``weight``, and ``port`` must each be in the
      0-65535 range.
    - When ``target`` is ``"."``, ``priority``, ``weight``, and
      ``port`` must all be ``0`` (RFC 2782 "service not available"
      convention).
    - When ``target`` is not ``"."``, ``port`` must be greater than
      0 (port 0 is IANA-reserved).

    Assumes the base ``SrvValueValidator`` has already caught missing
    or non-integer fields; entries that fail those checks are skipped
    here to avoid duplicated reasons. Not enabled by default; opt in
    by appending to ``SrvValue.VALIDATORS``.
    '''

    @classmethod
    def _as_int(cls, value, field):
        try:
            return int(value[field])
        except (KeyError, ValueError, TypeError):
            return None

    @classmethod
    def validate(cls, value_cls, data, _type):
        reasons = []
        for value in data:
            fields = {
                name: cls._as_int(value, name)
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


class SrvValue(EqualityTupleMixin, dict):
    VALIDATORS = [SrvValueValidator]

    @classmethod
    def _schema(cls):
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
    def parse_rdata_text(self, value):
        try:
            priority, weight, port, target = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            priority = int(priority)
        except ValueError:
            pass
        try:
            weight = int(weight)
        except ValueError:
            pass
        try:
            port = int(port)
        except ValueError:
            pass
        target = unquote(target)
        return {
            'priority': priority,
            'weight': weight,
            'port': port,
            'target': target,
        }

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'priority': int(value['priority']),
                'weight': int(value['weight']),
                'port': int(value['port']),
                'target': idna_encode(value['target']),
            }
        )

    @property
    def priority(self):
        return self['priority']

    @priority.setter
    def priority(self, value):
        self['priority'] = value

    @property
    def weight(self):
        return self['weight']

    @weight.setter
    def weight(self, value):
        self['weight'] = value

    @property
    def port(self):
        return self['port']

    @port.setter
    def port(self, value):
        self['port'] = value

    @property
    def target(self):
        return self['target']

    @target.setter
    def target(self, value):
        self['target'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return f"{self.priority} {self.weight} {self.port} {self.target}"

    def template(self, params):
        if '{' not in self.target:
            return self
        new = self.__class__(self)
        new.target = new.target.format(**params)
        return new

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (self.priority, self.weight, self.port, self.target)

    def __repr__(self):
        return f"'{self.priority} {self.weight} {self.port} {self.target}'"


class SrvRecord(ValuesMixin, Record):
    REFERENCES = (
        'https://datatracker.ietf.org/doc/html/rfc2782',
        'https://datatracker.ietf.org/doc/html/rfc6335',
    )
    _type = 'SRV'
    _value_type = SrvValue

    VALIDATORS = [SrvNameValidator]


Record.register_type(SrvRecord)
