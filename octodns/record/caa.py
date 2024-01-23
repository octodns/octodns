#
#
#

from ..equality import EqualityTupleMixin
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError


class CaaValue(EqualityTupleMixin, dict):
    # https://tools.ietf.org/html/rfc6844#page-5

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            flags, tag, value = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            flags = int(flags)
        except ValueError:
            pass
        tag = unquote(tag)
        value = unquote(value)
        return {'flags': flags, 'tag': tag, 'value': value}

    @classmethod
    def validate(cls, data, _type):
        reasons = []
        for value in data:
            try:
                flags = int(value.get('flags', 0))
                if flags < 0 or flags > 255:
                    reasons.append(f'invalid flags "{flags}"')
            except ValueError:
                reasons.append(f'invalid flags "{value["flags"]}"')

            if 'tag' not in value:
                reasons.append('missing tag')
            if 'value' not in value:
                reasons.append('missing value')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'flags': int(value.get('flags', 0)),
                'tag': value['tag'],
                'value': value['value'],
            }
        )

    @property
    def flags(self):
        return self['flags']

    @flags.setter
    def flags(self, value):
        self['flags'] = value

    @property
    def tag(self):
        return self['tag']

    @tag.setter
    def tag(self, value):
        self['tag'] = value

    @property
    def value(self):
        return self['value']

    @value.setter
    def value(self, value):
        self['value'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return f'{self.flags} {self.tag} {self.value}'

    def _equality_tuple(self):
        return (self.flags, self.tag, self.value)

    def __repr__(self):
        return f'{self.flags} {self.tag} "{self.value}"'


class CaaRecord(ValuesMixin, Record):
    _type = 'CAA'
    _value_type = CaaValue


Record.register_type(CaaRecord)
