#
#
#

from ..equality import EqualityTupleMixin
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError
from .validator import ValueValidator


class SshfpValueValidator(ValueValidator):
    @classmethod
    def validate(cls, value_cls, data, _type):
        reasons = []
        for value in data:
            try:
                algorithm = int(value['algorithm'])
                if algorithm not in value_cls.VALID_ALGORITHMS:
                    reasons.append(f'unrecognized algorithm "{algorithm}"')
            except KeyError:
                reasons.append('missing algorithm')
            except ValueError:
                reasons.append(f'invalid algorithm "{value["algorithm"]}"')
            # Start unset so the length check below can tell the difference
            # between a known-good fingerprint_type and a missing/invalid one.
            fingerprint_type = None
            try:
                fingerprint_type = int(value['fingerprint_type'])
                if fingerprint_type not in value_cls.VALID_FINGERPRINT_TYPES:
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
            # Only length-check when we have both a known fingerprint_type and
            # an actual fingerprint; unknown types and missing fingerprints
            # are already reported above and we don't want to stack a
            # confusing secondary error on top of them.
            elif fingerprint_type in value_cls.FINGERPRINT_LENGTHS:
                expected = value_cls.FINGERPRINT_LENGTHS[fingerprint_type]
                actual = len(value['fingerprint'])
                if actual != expected:
                    reasons.append(
                        f'fingerprint length {actual} does not match '
                        f'fingerprint_type {fingerprint_type} '
                        f'(expected {expected})'
                    )
        return reasons


class SshfpValue(EqualityTupleMixin, dict):
    VALID_ALGORITHMS = (1, 2, 3, 4)
    VALID_FINGERPRINT_TYPES = (1, 2)
    # Expected fingerprint hex-string length per fingerprint_type, from RFC
    # 4255/6594: type 1 = SHA-1 (160 bits, 40 hex chars), type 2 = SHA-256
    # (256 bits, 64 hex chars).
    FINGERPRINT_LENGTHS = {1: 40, 2: 64}

    VALIDATORS = [SshfpValueValidator]

    @classmethod
    def _schema(cls):
        return {
            'type': 'object',
            'required': ['algorithm', 'fingerprint_type', 'fingerprint'],
            'properties': {
                'algorithm': {'enum': list(cls.VALID_ALGORITHMS)},
                'fingerprint_type': {'enum': list(cls.VALID_FINGERPRINT_TYPES)},
                # fingerprint length-matches-type is enforced by octoDNS at
                # load time, not expressible cleanly in JSON Schema
                'fingerprint': {'type': 'string'},
            },
        }

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
        for validator in SshfpValue.VALIDATORS:
            reasons.extend(validator.validate(cls, data, _type))
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

    def template(self, params):
        if '{' not in self.fingerprint:
            return self
        new = self.__class__(self)
        new.fingerprint = new.fingerprint.format(**params)
        return new

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (self.algorithm, self.fingerprint_type, self.fingerprint)

    def __repr__(self):
        return f"'{self.algorithm} {self.fingerprint_type} {self.fingerprint}'"


class SshfpRecord(ValuesMixin, Record):
    REFERENCES = (
        'https://datatracker.ietf.org/doc/html/rfc4255',
        'https://datatracker.ietf.org/doc/html/rfc6594',
        'https://datatracker.ietf.org/doc/html/rfc7479',
        'https://datatracker.ietf.org/doc/html/rfc8709',
    )
    _type = 'SSHFP'
    _value_type = SshfpValue


Record.register_type(SshfpRecord)
