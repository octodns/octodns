#
#
#

import re

from ..equality import EqualityTupleMixin
from ..idna import idna_encode
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError


class UriValue(EqualityTupleMixin, dict):
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
    def validate(cls, data, _type):
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


# https://datatracker.ietf.org/doc/html/rfc7553
class UriRecord(ValuesMixin, Record):
    _type = 'URI'
    _value_type = UriValue
    _name_re = re.compile(r'^(\*|_[^\.]+)\.[^\.]+')

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = []
        if not cls._name_re.match(name):
            reasons.append('invalid name for URI record')
        reasons.extend(super().validate(name, fqdn, data))
        return reasons


Record.register_type(UriRecord)
