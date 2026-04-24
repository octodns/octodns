#
#
#

import re

from ..equality import EqualityTupleMixin
from ..idna import idna_encode
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError
from .validator import RecordValidator, ValueValidator


class UriNameValidator(RecordValidator):
    '''
    Validates that a URI record's name matches the
    ``_service._protocol`` pattern required by RFC 7553, or is a
    wildcard.
    '''

    _name_re = re.compile(r'^(\*|_[^\.]+)\.[^\.]+')

    def validate(self, record_cls, name, fqdn, data):
        if not self._name_re.match(name):
            return ['invalid name for URI record']
        return []


class UriValueValidator(ValueValidator):
    '''
    Validates URI rdata: priority and weight are present and
    integer-parsable, and target is non-empty.
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
                target = value['target']
                if not target:
                    reasons.append('missing target')
                    continue
                # actual validation of the target is non-trivial and specific
                # to the details of the schema etc. rfc3986 has support for
                # validation, but we don't currently require the module and
                # this seems too esoteric a use case to add it
            except KeyError:
                reasons.append('missing target')
        return reasons


class UriValue(EqualityTupleMixin, dict):
    @classmethod
    def _schema(cls):
        return {
            'type': 'object',
            'required': ['priority', 'weight', 'target'],
            'properties': {
                'priority': {'type': 'integer', 'minimum': 0, 'maximum': 65535},
                'weight': {'type': 'integer', 'minimum': 0, 'maximum': 65535},
                'target': {'type': 'string'},
            },
        }

    @classmethod
    def parse_rdata_text(self, value):
        try:
            priority, weight, target = value.split(' ')
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
        target = unquote(target)
        return {'priority': priority, 'weight': weight, 'target': target}

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'priority': int(value['priority']),
                'weight': int(value['weight']),
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
        return f'{self.priority} {self.weight} "{self.target}"'

    def template(self, params):
        if '{' not in self.target:
            return self
        new = self.__class__(self)
        new.target = new.target.format(**params)
        return new

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (self.priority, self.weight, self.target)

    def __repr__(self):
        return f"'{self.priority} {self.weight} \"{self.target}\"'"


class UriRecord(ValuesMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc7553',)
    _type = 'URI'
    _value_type = UriValue


Record.register_type(UriRecord)
Record.register_validator(UriNameValidator('uri-name'), types=['URI'])
Record.register_validator(UriValueValidator('uri-value'), types=['URI'])
