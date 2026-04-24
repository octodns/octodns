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

    def validate(self, record_cls, name, fqdn, data):
        if not self._name_re.match(name):
            return ['invalid name for SRV record']
        return []


class SrvValueValidator(ValueValidator):
    '''
    Validates SRV rdata: priority, weight, and port are present and
    integer-parsable, and target is a valid FQDN.
    '''

    def validate(self, value_cls, data, _type):
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


class SrvValue(EqualityTupleMixin, dict):
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


Record.register_type(SrvRecord)
Record.register_validator(SrvNameValidator('srv-name'), types=['SRV'])
Record.register_validator(SrvValueValidator('srv-value'), types=['SRV'])
