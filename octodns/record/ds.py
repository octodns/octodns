#
#
#

from logging import getLogger

from ..deprecation import deprecated
from ..equality import EqualityTupleMixin
from .base import Record, ValuesMixin
from .rr import RrParseError


class DsValue(EqualityTupleMixin, dict):
    # https://www.rfc-editor.org/rfc/rfc4034.html#section-5.1
    log = getLogger('DsValue')

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
    def validate(cls, data, _type):
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
                'digest': value['public_key'],
            }
        else:
            init = {
                'key_tag': int(value['key_tag']),
                'algorithm': int(value['algorithm']),
                'digest_type': int(value['digest_type']),
                'digest': value['digest'],
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

    def _equality_tuple(self):
        return (self.key_tag, self.algorithm, self.digest_type, self.digest)

    def __repr__(self):
        return (
            f'{self.key_tag} {self.algorithm} {self.digest_type} {self.digest}'
        )


class DsRecord(ValuesMixin, Record):
    _type = 'DS'
    _value_type = DsValue


Record.register_type(DsRecord)
