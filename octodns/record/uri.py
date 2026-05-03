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


class UriValueRfcValidator(ValueValidator):
    '''
    Strict URI rdata validator per RFC 7553 §4.

    - ``priority`` must be an integer in [0, 65535] (uint16).
    - ``weight`` must be an integer in [0, 65535] (uint16).

    Enabled as part of the ``strict`` validator set::

      manager:
        enabled:
          - strict
    '''

    def validate(self, value_cls, data, _type):
        reasons = []
        for value in data:
            for field in ('priority', 'weight'):
                if field not in value:
                    reasons.append(f'missing {field}')
                else:
                    try:
                        int_val = int(value[field])
                        if not 0 <= int_val <= 65535:
                            reasons.append(
                                f'invalid {field} "{int_val}"; must be 0-65535'
                            )
                    except (ValueError, TypeError):
                        reasons.append(f'invalid {field} "{value[field]}"')
            if 'target' not in value:
                reasons.append('missing target')
        return reasons


class UriValue(EqualityTupleMixin, dict):
    VALIDATORS = [
        UriValueValidator('uri-value', sets={'legacy'}),
        UriValueRfcValidator('uri-value-rfc', sets={'strict'}),
    ]

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


class UriNameRfcValidator(RecordValidator):
    '''
    Strict URI name validator per RFC 7553 §3 and RFC 6335 §5.1.

    Requires the first two labels of the record name to be
    ``_service._proto`` (``*._proto`` is still accepted for wildcards).
    Both label bodies (after the leading ``_``) must conform to the
    RFC 6335 §5.1 service name syntax: 1-15 characters, starting with a
    letter, ending with a letter or digit, containing only letters,
    digits, and hyphens, and with no consecutive hyphens.

    Enabled as part of the ``strict`` validator set::

      manager:
        enabled:
          - strict
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

    def validate(self, record_cls, name, fqdn, data):
        labels = name.split('.') if name else []
        if len(labels) < 2:
            return ['URI name must have at least two labels (_service._proto)']

        reasons = []
        service, proto = labels[0], labels[1]
        if service != '*' and not (
            service.startswith('_') and self._is_valid_service_name(service[1:])
        ):
            reasons.append(f'invalid URI service label "{service}"')
        if not (
            proto.startswith('_') and self._is_valid_service_name(proto[1:])
        ):
            reasons.append(f'invalid URI proto label "{proto}"')
        return reasons


class UriRecord(ValuesMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc7553',)
    _type = 'URI'
    _value_type = UriValue
    VALIDATORS = [
        UriNameValidator('uri-name', sets={'legacy'}),
        UriNameRfcValidator('uri-name-rfc', sets={'strict'}),
    ]


Record.register_type(UriRecord)
