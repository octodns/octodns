#
#
#

from ..equality import EqualityTupleMixin
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError


class NaptrValue(EqualityTupleMixin, dict):
    VALID_FLAGS = ('S', 'A', 'U', 'P')

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            (
                order,
                preference,
                flags,
                service,
                regexp,
                replacement,
            ) = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            order = int(order)
            preference = int(preference)
        except ValueError:
            pass
        flags = unquote(flags)
        service = unquote(service)
        regexp = unquote(regexp)
        replacement = unquote(replacement)
        return {
            'order': order,
            'preference': preference,
            'flags': flags,
            'service': service,
            'regexp': regexp,
            'replacement': replacement,
        }

    @classmethod
    def validate(cls, data, _type):
        reasons = []
        for value in data:
            try:
                int(value['order'])
            except KeyError:
                reasons.append('missing order')
            except ValueError:
                reasons.append(f'invalid order "{value["order"]}"')
            try:
                int(value['preference'])
            except KeyError:
                reasons.append('missing preference')
            except ValueError:
                reasons.append(f'invalid preference "{value["preference"]}"')
            try:
                flags = value['flags']
                if flags not in cls.VALID_FLAGS:
                    reasons.append(f'unrecognized flags "{flags}"')
            except KeyError:
                reasons.append('missing flags')

            # TODO: validate these... they're non-trivial
            for k in ('service', 'regexp', 'replacement'):
                if k not in value:
                    reasons.append(f'missing {k}')

        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'order': int(value['order']),
                'preference': int(value['preference']),
                'flags': value['flags'],
                'service': value['service'],
                'regexp': value['regexp'],
                'replacement': value['replacement'],
            }
        )

    @property
    def order(self):
        return self['order']

    @order.setter
    def order(self, value):
        self['order'] = value

    @property
    def preference(self):
        return self['preference']

    @preference.setter
    def preference(self, value):
        self['preference'] = value

    @property
    def flags(self):
        return self['flags']

    @flags.setter
    def flags(self, value):
        self['flags'] = value

    @property
    def service(self):
        return self['service']

    @service.setter
    def service(self, value):
        self['service'] = value

    @property
    def regexp(self):
        return self['regexp']

    @regexp.setter
    def regexp(self, value):
        self['regexp'] = value

    @property
    def replacement(self):
        return self['replacement']

    @replacement.setter
    def replacement(self, value):
        self['replacement'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return f'{self.order} {self.preference} {self.flags} {self.service} {self.regexp} {self.replacement}'

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (
            self.order,
            self.preference,
            self.flags,
            self.service,
            self.regexp,
            self.replacement,
        )

    def __repr__(self):
        flags = self.flags if self.flags is not None else ''
        service = self.service if self.service is not None else ''
        regexp = self.regexp if self.regexp is not None else ''
        return (
            f"'{self.order} {self.preference} \"{flags}\" \"{service}\" "
            f"\"{regexp}\" {self.replacement}'"
        )


class NaptrRecord(ValuesMixin, Record):
    _type = 'NAPTR'
    _value_type = NaptrValue


Record.register_type(NaptrRecord)
