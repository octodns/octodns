#
#
#

from ..equality import EqualityTupleMixin
from .base import Record, ValuesMixin
from .rr import RrParseError


class DsValue(EqualityTupleMixin, dict):
    # https://www.rfc-editor.org/rfc/rfc4034.html#section-2.1

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            flags, protocol, algorithm, public_key = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            flags = int(flags)
        except ValueError:
            pass
        try:
            protocol = int(protocol)
        except ValueError:
            pass
        try:
            algorithm = int(algorithm)
        except ValueError:
            pass
        return {
            'flags': flags,
            'protocol': protocol,
            'algorithm': algorithm,
            'public_key': public_key,
        }

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            try:
                int(value['flags'])
            except KeyError:
                reasons.append('missing flags')
            except ValueError:
                reasons.append(f'invalid flags "{value["flags"]}"')
            try:
                int(value['protocol'])
            except KeyError:
                reasons.append('missing protocol')
            except ValueError:
                reasons.append(f'invalid protocol "{value["protocol"]}"')
            try:
                int(value['algorithm'])
            except KeyError:
                reasons.append('missing algorithm')
            except ValueError:
                reasons.append(f'invalid algorithm "{value["algorithm"]}"')
            if 'public_key' not in value:
                reasons.append('missing public_key')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'flags': int(value['flags']),
                'protocol': int(value['protocol']),
                'algorithm': int(value['algorithm']),
                'public_key': value['public_key'],
            }
        )

    @property
    def flags(self):
        return self['flags']

    @flags.setter
    def flags(self, value):
        self['flags'] = value

    @property
    def protocol(self):
        return self['protocol']

    @protocol.setter
    def protocol(self, value):
        self['protocol'] = value

    @property
    def algorithm(self):
        return self['algorithm']

    @algorithm.setter
    def algorithm(self, value):
        self['algorithm'] = value

    @property
    def public_key(self):
        return self['public_key']

    @public_key.setter
    def public_key(self, value):
        self['public_key'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return (
            f'{self.flags} {self.protocol} {self.algorithm} {self.public_key}'
        )

    def _equality_tuple(self):
        return (self.flags, self.protocol, self.algorithm, self.public_key)

    def __repr__(self):
        return (
            f'{self.flags} {self.protocol} {self.algorithm} {self.public_key}'
        )


class DsRecord(ValuesMixin, Record):
    _type = 'DS'
    _value_type = DsValue


Record.register_type(DsRecord)
