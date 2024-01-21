#
#
#

from ..equality import EqualityTupleMixin
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError


class SshfpValue(EqualityTupleMixin, dict):
    VALID_ALGORITHMS = (1, 2, 3, 4)
    VALID_FINGERPRINT_TYPES = (1, 2)

    @classmethod
    def parse_rdata_text(self, value):
        try:
            algorithm, fingerprint_type, fingerprint = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            algorithm = int(algorithm)
        except ValueError:
            pass
        try:
            fingerprint_type = int(fingerprint_type)
        except ValueError:
            pass
        fingerprint = unquote(fingerprint)
        return {
            'algorithm': algorithm,
            'fingerprint_type': fingerprint_type,
            'fingerprint': fingerprint,
        }

    @classmethod
    def validate(cls, data, _type):
        reasons = []
        for value in data:
            try:
                algorithm = int(value['algorithm'])
                if algorithm not in cls.VALID_ALGORITHMS:
                    reasons.append(f'unrecognized algorithm "{algorithm}"')
            except KeyError:
                reasons.append('missing algorithm')
            except ValueError:
                reasons.append(f'invalid algorithm "{value["algorithm"]}"')
            try:
                fingerprint_type = int(value['fingerprint_type'])
                if fingerprint_type not in cls.VALID_FINGERPRINT_TYPES:
                    reasons.append(
                        'unrecognized fingerprint_type ' f'"{fingerprint_type}"'
                    )
            except KeyError:
                reasons.append('missing fingerprint_type')
            except ValueError:
                reasons.append(
                    'invalid fingerprint_type ' f'"{value["fingerprint_type"]}"'
                )
            if 'fingerprint' not in value:
                reasons.append('missing fingerprint')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'algorithm': int(value['algorithm']),
                'fingerprint_type': int(value['fingerprint_type']),
                'fingerprint': value['fingerprint'],
            }
        )

    @property
    def algorithm(self):
        return self['algorithm']

    @algorithm.setter
    def algorithm(self, value):
        self['algorithm'] = value

    @property
    def fingerprint_type(self):
        return self['fingerprint_type']

    @fingerprint_type.setter
    def fingerprint_type(self, value):
        self['fingerprint_type'] = value

    @property
    def fingerprint(self):
        return self['fingerprint']

    @fingerprint.setter
    def fingerprint(self, value):
        self['fingerprint'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return f'{self.algorithm} {self.fingerprint_type} {self.fingerprint}'

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (self.algorithm, self.fingerprint_type, self.fingerprint)

    def __repr__(self):
        return f"'{self.algorithm} {self.fingerprint_type} {self.fingerprint}'"


class SshfpRecord(ValuesMixin, Record):
    _type = 'SSHFP'
    _value_type = SshfpValue


Record.register_type(SshfpRecord)
