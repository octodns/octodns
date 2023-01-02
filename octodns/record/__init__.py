#
#
#

import re

from fqdn import FQDN

from ..equality import EqualityTupleMixin
from ..idna import idna_encode
from .geo import GeoCodes, GeoValue

from .base import Record, ValueMixin, ValuesMixin
from .change import Create, Delete, Update
from .exception import RecordException, ValidationError
from .rr import Rr, RrParseError
from .target import (
    AliasRecord,
    AliasValue,
    CnameRecord,
    CnameValue,
    DnameRecord,
    DnameValue,
    NsValue,
    NsRecord,
    PtrValue,
    PtrRecord,
)
from .ipaddress import ARecord, AaaaRecord, Ipv4Address, Ipv6Address

# quell warnings
ARecord
AaaaRecord
AliasRecord
AliasValue
CnameRecord
CnameValue
Create
Delete
DnameRecord
DnameValue
GeoCodes
GeoValue
Ipv4Address
Ipv6Address
NsRecord
NsValue
PtrRecord
PtrValue
RecordException
Rr
Update
ValidationError
ValueMixin
ValuesMixin


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
        return {'flags': flags, 'tag': tag, 'value': value}

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
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


class LocValue(EqualityTupleMixin, dict):
    # TODO: this does not really match the RFC, but it's stuck using the details
    # of how the type was impelemented. Would be nice to rework things to match
    # while maintaining backwards compatibility.
    # https://www.rfc-editor.org/rfc/rfc1876.html

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            value = value.replace('m', '')
            (
                lat_degrees,
                lat_minutes,
                lat_seconds,
                lat_direction,
                long_degrees,
                long_minutes,
                long_seconds,
                long_direction,
                altitude,
                size,
                precision_horz,
                precision_vert,
            ) = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            lat_degrees = int(lat_degrees)
        except ValueError:
            pass
        try:
            lat_minutes = int(lat_minutes)
        except ValueError:
            pass
        try:
            long_degrees = int(long_degrees)
        except ValueError:
            pass
        try:
            long_minutes = int(long_minutes)
        except ValueError:
            pass
        try:
            lat_seconds = float(lat_seconds)
        except ValueError:
            pass
        try:
            long_seconds = float(long_seconds)
        except ValueError:
            pass
        try:
            altitude = float(altitude)
        except ValueError:
            pass
        try:
            size = float(size)
        except ValueError:
            pass
        try:
            precision_horz = float(precision_horz)
        except ValueError:
            pass
        try:
            precision_vert = float(precision_vert)
        except ValueError:
            pass
        return {
            'lat_degrees': lat_degrees,
            'lat_minutes': lat_minutes,
            'lat_seconds': lat_seconds,
            'lat_direction': lat_direction,
            'long_degrees': long_degrees,
            'long_minutes': long_minutes,
            'long_seconds': long_seconds,
            'long_direction': long_direction,
            'altitude': altitude,
            'size': size,
            'precision_horz': precision_horz,
            'precision_vert': precision_vert,
        }

    @classmethod
    def validate(cls, data, _type):
        int_keys = [
            'lat_degrees',
            'lat_minutes',
            'long_degrees',
            'long_minutes',
        ]

        float_keys = [
            'lat_seconds',
            'long_seconds',
            'altitude',
            'size',
            'precision_horz',
            'precision_vert',
        ]

        direction_keys = ['lat_direction', 'long_direction']

        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            for key in int_keys:
                try:
                    int(value[key])
                    if (
                        (
                            key == 'lat_degrees'
                            and not 0 <= int(value[key]) <= 90
                        )
                        or (
                            key == 'long_degrees'
                            and not 0 <= int(value[key]) <= 180
                        )
                        or (
                            key in ['lat_minutes', 'long_minutes']
                            and not 0 <= int(value[key]) <= 59
                        )
                    ):
                        reasons.append(
                            f'invalid value for {key} ' f'"{value[key]}"'
                        )
                except KeyError:
                    reasons.append(f'missing {key}')
                except ValueError:
                    reasons.append(f'invalid {key} "{value[key]}"')

            for key in float_keys:
                try:
                    float(value[key])
                    if (
                        (
                            key in ['lat_seconds', 'long_seconds']
                            and not 0 <= float(value[key]) <= 59.999
                        )
                        or (
                            key == 'altitude'
                            and not -100000.00
                            <= float(value[key])
                            <= 42849672.95
                        )
                        or (
                            key in ['size', 'precision_horz', 'precision_vert']
                            and not 0 <= float(value[key]) <= 90000000.00
                        )
                    ):
                        reasons.append(
                            f'invalid value for {key} ' f'"{value[key]}"'
                        )
                except KeyError:
                    reasons.append(f'missing {key}')
                except ValueError:
                    reasons.append(f'invalid {key} "{value[key]}"')

            for key in direction_keys:
                try:
                    str(value[key])
                    if key == 'lat_direction' and value[key] not in ['N', 'S']:
                        reasons.append(
                            f'invalid direction for {key} ' f'"{value[key]}"'
                        )
                    if key == 'long_direction' and value[key] not in ['E', 'W']:
                        reasons.append(
                            f'invalid direction for {key} ' f'"{value[key]}"'
                        )
                except KeyError:
                    reasons.append(f'missing {key}')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'lat_degrees': int(value['lat_degrees']),
                'lat_minutes': int(value['lat_minutes']),
                'lat_seconds': float(value['lat_seconds']),
                'lat_direction': value['lat_direction'].upper(),
                'long_degrees': int(value['long_degrees']),
                'long_minutes': int(value['long_minutes']),
                'long_seconds': float(value['long_seconds']),
                'long_direction': value['long_direction'].upper(),
                'altitude': float(value['altitude']),
                'size': float(value['size']),
                'precision_horz': float(value['precision_horz']),
                'precision_vert': float(value['precision_vert']),
            }
        )

    @property
    def lat_degrees(self):
        return self['lat_degrees']

    @lat_degrees.setter
    def lat_degrees(self, value):
        self['lat_degrees'] = value

    @property
    def lat_minutes(self):
        return self['lat_minutes']

    @lat_minutes.setter
    def lat_minutes(self, value):
        self['lat_minutes'] = value

    @property
    def lat_seconds(self):
        return self['lat_seconds']

    @lat_seconds.setter
    def lat_seconds(self, value):
        self['lat_seconds'] = value

    @property
    def lat_direction(self):
        return self['lat_direction']

    @lat_direction.setter
    def lat_direction(self, value):
        self['lat_direction'] = value

    @property
    def long_degrees(self):
        return self['long_degrees']

    @long_degrees.setter
    def long_degrees(self, value):
        self['long_degrees'] = value

    @property
    def long_minutes(self):
        return self['long_minutes']

    @long_minutes.setter
    def long_minutes(self, value):
        self['long_minutes'] = value

    @property
    def long_seconds(self):
        return self['long_seconds']

    @long_seconds.setter
    def long_seconds(self, value):
        self['long_seconds'] = value

    @property
    def long_direction(self):
        return self['long_direction']

    @long_direction.setter
    def long_direction(self, value):
        self['long_direction'] = value

    @property
    def altitude(self):
        return self['altitude']

    @altitude.setter
    def altitude(self, value):
        self['altitude'] = value

    @property
    def size(self):
        return self['size']

    @size.setter
    def size(self, value):
        self['size'] = value

    @property
    def precision_horz(self):
        return self['precision_horz']

    @precision_horz.setter
    def precision_horz(self, value):
        self['precision_horz'] = value

    @property
    def precision_vert(self):
        return self['precision_vert']

    @precision_vert.setter
    def precision_vert(self, value):
        self['precision_vert'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return f'{self.lat_degrees} {self.lat_minutes} {self.lat_seconds} {self.lat_direction} {self.long_degrees} {self.long_minutes} {self.long_seconds} {self.long_direction} {self.altitude}m {self.size}m {self.precision_horz}m {self.precision_vert}m'

    def __hash__(self):
        return hash(
            (
                self.lat_degrees,
                self.lat_minutes,
                self.lat_seconds,
                self.lat_direction,
                self.long_degrees,
                self.long_minutes,
                self.long_seconds,
                self.long_direction,
                self.altitude,
                self.size,
                self.precision_horz,
                self.precision_vert,
            )
        )

    def _equality_tuple(self):
        return (
            self.lat_degrees,
            self.lat_minutes,
            self.lat_seconds,
            self.lat_direction,
            self.long_degrees,
            self.long_minutes,
            self.long_seconds,
            self.long_direction,
            self.altitude,
            self.size,
            self.precision_horz,
            self.precision_vert,
        )

    def __repr__(self):
        return (
            f"'{self.lat_degrees} {self.lat_minutes} "
            f"{self.lat_seconds:.3f} {self.lat_direction} "
            f"{self.long_degrees} {self.long_minutes} "
            f"{self.long_seconds:.3f} {self.long_direction} "
            f"{self.altitude:.2f}m {self.size:.2f}m "
            f"{self.precision_horz:.2f}m {self.precision_vert:.2f}m'"
        )


class LocRecord(ValuesMixin, Record):
    _type = 'LOC'
    _value_type = LocValue


Record.register_type(LocRecord)


class MxValue(EqualityTupleMixin, dict):
    @classmethod
    def parse_rdata_text(cls, value):
        try:
            preference, exchange = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            preference = int(preference)
        except ValueError:
            pass
        return {'preference': preference, 'exchange': exchange}

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            try:
                try:
                    int(value['preference'])
                except KeyError:
                    int(value['priority'])
            except KeyError:
                reasons.append('missing preference')
            except ValueError:
                reasons.append(f'invalid preference "{value["preference"]}"')
            exchange = None
            try:
                exchange = value.get('exchange', None) or value['value']
                if not exchange:
                    reasons.append('missing exchange')
                    continue
                exchange = idna_encode(exchange)
                if (
                    exchange != '.'
                    and not FQDN(exchange, allow_underscores=True).is_valid
                ):
                    reasons.append(
                        f'Invalid MX exchange "{exchange}" is not '
                        'a valid FQDN.'
                    )
                elif not exchange.endswith('.'):
                    reasons.append(f'MX value "{exchange}" missing trailing .')
            except KeyError:
                reasons.append('missing exchange')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        # RFC1035 says preference, half the providers use priority
        try:
            preference = value['preference']
        except KeyError:
            preference = value['priority']
        # UNTIL 1.0 remove value fallback
        try:
            exchange = value['exchange']
        except KeyError:
            exchange = value['value']
        super().__init__(
            {'preference': int(preference), 'exchange': idna_encode(exchange)}
        )

    @property
    def preference(self):
        return self['preference']

    @preference.setter
    def preference(self, value):
        self['preference'] = value

    @property
    def exchange(self):
        return self['exchange']

    @exchange.setter
    def exchange(self, value):
        self['exchange'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return f'{self.preference} {self.exchange}'

    def __hash__(self):
        return hash((self.preference, self.exchange))

    def _equality_tuple(self):
        return (self.preference, self.exchange)

    def __repr__(self):
        return f"'{self.preference} {self.exchange}'"


class MxRecord(ValuesMixin, Record):
    _type = 'MX'
    _value_type = MxValue


Record.register_type(MxRecord)


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
        if not isinstance(data, (list, tuple)):
            data = (data,)
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
        return {
            'algorithm': algorithm,
            'fingerprint_type': fingerprint_type,
            'fingerprint': fingerprint,
        }

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
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


class _ChunkedValuesMixin(ValuesMixin):
    CHUNK_SIZE = 255
    _unescaped_semicolon_re = re.compile(r'\w;')

    def chunked_value(self, value):
        value = value.replace('"', '\\"')
        vs = [
            value[i : i + self.CHUNK_SIZE]
            for i in range(0, len(value), self.CHUNK_SIZE)
        ]
        vs = '" "'.join(vs)
        return f'"{vs}"'

    @property
    def chunked_values(self):
        values = []
        for v in self.values:
            values.append(self.chunked_value(v))
        return values


class _ChunkedValue(str):
    _unescaped_semicolon_re = re.compile(r'\w;')

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            return value.replace(';', '\\;')
        except AttributeError:
            return value

    @classmethod
    def validate(cls, data, _type):
        if not data:
            return ['missing value(s)']
        elif not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            if cls._unescaped_semicolon_re.search(value):
                reasons.append(f'unescaped ; in "{value}"')
        return reasons

    @classmethod
    def process(cls, values):
        ret = []
        for v in values:
            if v and v[0] == '"':
                v = v[1:-1]
            ret.append(cls(v.replace('" "', '')))
        return ret

    @property
    def rdata_text(self):
        return self


class SpfRecord(_ChunkedValuesMixin, Record):
    _type = 'SPF'
    _value_type = _ChunkedValue


Record.register_type(SpfRecord)


class SrvValue(EqualityTupleMixin, dict):
    @classmethod
    def parse_rdata_text(self, value):
        try:
            priority, weight, port, target = value.split(' ')
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
        try:
            port = int(port)
        except ValueError:
            pass
        return {
            'priority': priority,
            'weight': weight,
            'port': port,
            'target': target,
        }

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
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
                int(value['port'])
            except KeyError:
                reasons.append('missing port')
            except ValueError:
                reasons.append(f'invalid port "{value["port"]}"')
            try:
                target = value['target']
                if not target:
                    reasons.append('missing target')
                    continue
                target = idna_encode(target)
                if not target.endswith('.'):
                    reasons.append(f'SRV value "{target}" missing trailing .')
                if (
                    target != '.'
                    and not FQDN(target, allow_underscores=True).is_valid
                ):
                    reasons.append(
                        f'Invalid SRV target "{target}" is not a valid FQDN.'
                    )
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
                'port': int(value['port']),
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
    def port(self):
        return self['port']

    @port.setter
    def port(self, value):
        self['port'] = value

    @property
    def target(self):
        return self['target']

    @target.setter
    def target(self, value):
        self['target'] = value

    @property
    def data(self):
        return self

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (self.priority, self.weight, self.port, self.target)

    def __repr__(self):
        return f"'{self.priority} {self.weight} {self.port} {self.target}'"


class SrvRecord(ValuesMixin, Record):
    _type = 'SRV'
    _value_type = SrvValue
    _name_re = re.compile(r'^(\*|_[^\.]+)\.[^\.]+')

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = []
        if not cls._name_re.match(name):
            reasons.append('invalid name for SRV record')
        reasons.extend(super().validate(name, fqdn, data))
        return reasons


Record.register_type(SrvRecord)


class TlsaValue(EqualityTupleMixin, dict):
    @classmethod
    def parse_rdata_text(self, value):
        try:
            (
                certificate_usage,
                selector,
                matching_type,
                certificate_association_data,
            ) = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            certificate_usage = int(certificate_usage)
        except ValueError:
            pass
        try:
            selector = int(selector)
        except ValueError:
            pass
        try:
            matching_type = int(matching_type)
        except ValueError:
            pass
        return {
            'certificate_usage': certificate_usage,
            'selector': selector,
            'matching_type': matching_type,
            'certificate_association_data': certificate_association_data,
        }

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            try:
                certificate_usage = int(value.get('certificate_usage', 0))
                if certificate_usage < 0 or certificate_usage > 3:
                    reasons.append(
                        f'invalid certificate_usage ' f'"{certificate_usage}"'
                    )
            except ValueError:
                reasons.append(
                    f'invalid certificate_usage '
                    f'"{value["certificate_usage"]}"'
                )

            try:
                selector = int(value.get('selector', 0))
                if selector < 0 or selector > 1:
                    reasons.append(f'invalid selector "{selector}"')
            except ValueError:
                reasons.append(f'invalid selector "{value["selector"]}"')

            try:
                matching_type = int(value.get('matching_type', 0))
                if matching_type < 0 or matching_type > 2:
                    reasons.append(f'invalid matching_type "{matching_type}"')
            except ValueError:
                reasons.append(
                    f'invalid matching_type ' f'"{value["matching_type"]}"'
                )

            if 'certificate_usage' not in value:
                reasons.append('missing certificate_usage')
            if 'selector' not in value:
                reasons.append('missing selector')
            if 'matching_type' not in value:
                reasons.append('missing matching_type')
            if 'certificate_association_data' not in value:
                reasons.append('missing certificate_association_data')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'certificate_usage': int(value.get('certificate_usage', 0)),
                'selector': int(value.get('selector', 0)),
                'matching_type': int(value.get('matching_type', 0)),
                # force it to a string, in case the hex has only numerical
                # values and it was converted to an int at some point
                # TODO: this needed on any others?
                'certificate_association_data': str(
                    value['certificate_association_data']
                ),
            }
        )

    @property
    def certificate_usage(self):
        return self['certificate_usage']

    @certificate_usage.setter
    def certificate_usage(self, value):
        self['certificate_usage'] = value

    @property
    def selector(self):
        return self['selector']

    @selector.setter
    def selector(self, value):
        self['selector'] = value

    @property
    def matching_type(self):
        return self['matching_type']

    @matching_type.setter
    def matching_type(self, value):
        self['matching_type'] = value

    @property
    def certificate_association_data(self):
        return self['certificate_association_data']

    @certificate_association_data.setter
    def certificate_association_data(self, value):
        self['certificate_association_data'] = value

    @property
    def rdata_text(self):
        return f'{self.certificate_usage} {self.selector} {self.matching_type} {self.certificate_association_data}'

    def _equality_tuple(self):
        return (
            self.certificate_usage,
            self.selector,
            self.matching_type,
            self.certificate_association_data,
        )

    def __repr__(self):
        return (
            f"'{self.certificate_usage} {self.selector} '"
            f"'{self.matching_type} {self.certificate_association_data}'"
        )


class TlsaRecord(ValuesMixin, Record):
    _type = 'TLSA'
    _value_type = TlsaValue


Record.register_type(TlsaRecord)


class _TxtValue(_ChunkedValue):
    pass


class TxtRecord(_ChunkedValuesMixin, Record):
    _type = 'TXT'
    _value_type = _TxtValue


Record.register_type(TxtRecord)


class UrlfwdValue(EqualityTupleMixin, dict):
    VALID_CODES = (301, 302)
    VALID_MASKS = (0, 1, 2)
    VALID_QUERY = (0, 1)

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            try:
                code = int(value['code'])
                if code not in cls.VALID_CODES:
                    reasons.append(f'unrecognized return code "{code}"')
            except KeyError:
                reasons.append('missing code')
            except ValueError:
                reasons.append(f'invalid return code "{value["code"]}"')
            try:
                masking = int(value['masking'])
                if masking not in cls.VALID_MASKS:
                    reasons.append(f'unrecognized masking setting "{masking}"')
            except KeyError:
                reasons.append('missing masking')
            except ValueError:
                reasons.append(f'invalid masking setting "{value["masking"]}"')
            try:
                query = int(value['query'])
                if query not in cls.VALID_QUERY:
                    reasons.append(f'unrecognized query setting "{query}"')
            except KeyError:
                reasons.append('missing query')
            except ValueError:
                reasons.append(f'invalid query setting "{value["query"]}"')
            for k in ('path', 'target'):
                if k not in value:
                    reasons.append(f'missing {k}')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'path': value['path'],
                'target': value['target'],
                'code': int(value['code']),
                'masking': int(value['masking']),
                'query': int(value['query']),
            }
        )

    @property
    def path(self):
        return self['path']

    @path.setter
    def path(self, value):
        self['path'] = value

    @property
    def target(self):
        return self['target']

    @target.setter
    def target(self, value):
        self['target'] = value

    @property
    def code(self):
        return self['code']

    @code.setter
    def code(self, value):
        self['code'] = value

    @property
    def masking(self):
        return self['masking']

    @masking.setter
    def masking(self, value):
        self['masking'] = value

    @property
    def query(self):
        return self['query']

    @query.setter
    def query(self, value):
        self['query'] = value

    def _equality_tuple(self):
        return (self.path, self.target, self.code, self.masking, self.query)

    def __hash__(self):
        return hash(
            (self.path, self.target, self.code, self.masking, self.query)
        )

    def __repr__(self):
        return f'"{self.path}" "{self.target}" {self.code} {self.masking} {self.query}'


class UrlfwdRecord(ValuesMixin, Record):
    _type = 'URLFWD'
    _value_type = UrlfwdValue


Record.register_type(UrlfwdRecord)
