#
#
#

import re
from logging import getLogger

from ..deprecation import deprecated
from ..equality import EqualityTupleMixin
from .base import Record, ValuesMixin
from .rr import RrParseError
from .validator import ValueValidator


class DsValueValidator(ValueValidator):
    '''
    Validates DS rdata. Supports both the current field names
    (``key_tag``, ``algorithm``, ``digest_type``, ``digest``) and the
    deprecated legacy field names (``flags``, ``protocol``,
    ``algorithm``, ``public_key``), which will be removed in 2.0.
    '''

    def validate(self, value_cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            # we need to validate both "old" style field names and new
            # it is safe to assume if public_key or flags are defined then it is "old" style
            # A DS record without public_key doesn't make any sense and shouldn't have validated previously
            if "public_key" in value or "flags" in value:
                deprecated(
                    'DS properties "algorithm", "flags", "public_key", and "protocol" support is DEPRECATED and will be removed in 2.0',
                    stacklevel=99,
                )
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

            else:
                try:
                    int(value['key_tag'])
                except KeyError:
                    reasons.append('missing key_tag')
                except ValueError:
                    reasons.append(f'invalid key_tag "{value["key_tag"]}"')
                try:
                    int(value['algorithm'])
                except KeyError:
                    reasons.append('missing algorithm')
                except ValueError:
                    reasons.append(f'invalid algorithm "{value["algorithm"]}"')
                try:
                    int(value['digest_type'])
                except KeyError:
                    reasons.append('missing digest_type')
                except ValueError:
                    reasons.append(
                        f'invalid digest_type "{value["digest_type"]}"'
                    )
                if 'digest' not in value:
                    reasons.append('missing digest')
        return reasons


class DsValueRfcValidator(ValueValidator):
    '''
    Strict DS rdata validator per RFC 4034 §5.1, RFC 4509, and RFC 6605.

    - ``key_tag`` must be in [0, 65535] (uint16).
    - ``algorithm`` must be in [0, 255] (uint8).
    - ``digest_type`` must be in [0, 255] (uint8).
    - ``digest`` must be a valid hexadecimal string.
    - For known digest types, the digest length is enforced:
      type 1 (SHA-1) = 40 hex chars, type 2 (SHA-256) = 64 hex chars,
      type 4 (SHA-384) = 96 hex chars.

    The deprecated legacy field names (``flags``, ``protocol``,
    ``public_key``) are not accepted in strict mode.

    Enabled as part of the ``strict`` validator set::

      manager:
        enabled:
          - strict
    '''

    _hex_re = re.compile(r'^[0-9a-fA-F]+$')
    _digest_type_lengths = {1: 40, 2: 64, 4: 96}

    def validate(self, value_cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            digest_type = None
            for field, max_val in (
                ('key_tag', 65535),
                ('algorithm', 255),
                ('digest_type', 255),
            ):
                if field not in value:
                    reasons.append(f'missing {field}')
                else:
                    try:
                        int_val = int(value[field])
                        if not 0 <= int_val <= max_val:
                            reasons.append(
                                f'invalid {field} "{int_val}"; must be 0-{max_val}'
                            )
                        elif field == 'digest_type':
                            digest_type = int_val
                    except (ValueError, TypeError):
                        reasons.append(f'invalid {field} "{value[field]}"')

            if 'digest' not in value:
                reasons.append('missing digest')
            else:
                digest = value['digest']
                if not digest or not self._hex_re.match(str(digest)):
                    reasons.append(f'invalid digest "{digest}"; must be hex')
                elif digest_type in self._digest_type_lengths:
                    expected = self._digest_type_lengths[digest_type]
                    if len(str(digest)) != expected:
                        reasons.append(
                            f'digest must be {expected} hex characters for digest_type {digest_type}'
                        )
        return reasons


class DsValue(EqualityTupleMixin, dict):
    # https://www.rfc-editor.org/rfc/rfc4034.html#section-5.1
    log = getLogger('DsValue')

    VALIDATORS = [
        DsValueValidator('ds-value', sets={'legacy'}),
        DsValueRfcValidator('ds-value-rfc', sets={'strict'}),
    ]

    @classmethod
    def _schema(cls):
        return {
            'type': 'object',
            'anyOf': [
                {'required': ['key_tag', 'algorithm', 'digest_type', 'digest']},
                # deprecated legacy form kept valid until 2.0
                {'required': ['flags', 'protocol', 'algorithm', 'public_key']},
            ],
            'properties': {
                'key_tag': {'type': 'integer', 'minimum': 0, 'maximum': 65535},
                'algorithm': {'type': 'integer', 'minimum': 0, 'maximum': 255},
                'digest_type': {
                    'type': 'integer',
                    'minimum': 0,
                    'maximum': 255,
                },
                'digest': {'type': 'string'},
                'flags': {'type': 'integer'},
                'protocol': {'type': 'integer'},
                'public_key': {'type': 'string'},
            },
        }

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            key_tag, algorithm, digest_type, digest = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            key_tag = int(key_tag)
        except ValueError:
            pass
        try:
            algorithm = int(algorithm)
        except ValueError:
            pass
        try:
            digest_type = int(digest_type)
        except ValueError:
            pass
        return {
            'key_tag': key_tag,
            'algorithm': algorithm,
            'digest_type': digest_type,
            'digest': digest,
        }

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        # we need to instantiate both based on "old" style field names and new
        # it is safe to assume if public_key or flags are defined then it is "old" style
        if "public_key" in value or "flags" in value:
            init = {
                'key_tag': int(value['flags']),
                'algorithm': int(value['protocol']),
                'digest_type': int(value['algorithm']),
                'digest': str(value['public_key']).lower(),
            }
        else:
            init = {
                'key_tag': int(value['key_tag']),
                'algorithm': int(value['algorithm']),
                'digest_type': int(value['digest_type']),
                'digest': str(value['digest']).lower(),
            }
        super().__init__(init)

    @property
    def key_tag(self):
        return self['key_tag']

    @key_tag.setter
    def key_tag(self, value):
        self['key_tag'] = value

    @property
    def algorithm(self):
        return self['algorithm']

    @algorithm.setter
    def algorithm(self, value):
        self['algorithm'] = value

    @property
    def digest_type(self):
        return self['digest_type']

    @digest_type.setter
    def digest_type(self, value):
        self['digest_type'] = value

    @property
    def digest(self):
        return self['digest']

    @digest.setter
    def digest(self, value):
        self['digest'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return (
            f'{self.key_tag} {self.algorithm} {self.digest_type} {self.digest}'
        )

    def template(self, params):
        if '{' not in self.digest:
            return self
        new = self.__class__(self)
        new.digest = new.digest.format(**params)
        return new

    def _equality_tuple(self):
        return (self.key_tag, self.algorithm, self.digest_type, self.digest)

    def __repr__(self):
        return (
            f'{self.key_tag} {self.algorithm} {self.digest_type} {self.digest}'
        )


class DsRecord(ValuesMixin, Record):
    REFERENCES = (
        'https://datatracker.ietf.org/doc/html/rfc4034',
        'https://datatracker.ietf.org/doc/html/rfc4035',
        'https://datatracker.ietf.org/doc/html/rfc4509',
        'https://datatracker.ietf.org/doc/html/rfc6605',
        'https://datatracker.ietf.org/doc/html/rfc6840',
        'https://datatracker.ietf.org/doc/html/rfc8080',
        'https://datatracker.ietf.org/doc/html/rfc8624',
    )
    _type = 'DS'
    _value_type = DsValue


Record.register_type(DsRecord)
