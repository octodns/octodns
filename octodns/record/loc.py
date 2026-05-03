#
#
#

from ..equality import EqualityTupleMixin
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError
from .validator import ValueValidator


class LocValueValidator(ValueValidator):
    '''
    Validates LOC rdata per RFC 1876: latitude/longitude degrees and
    minutes are integers in their respective ranges, the seconds,
    altitude, size, and precision fields are floats in range, and the
    ``lat_direction`` (N/S) and ``long_direction`` (E/W) are valid
    cardinal directions.
    '''

    def validate(self, value_cls, data, _type):
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


class LocValue(EqualityTupleMixin, dict):
    # TODO: this does not really match the RFC, but it's stuck using the details
    # of how the type was impelemented. Would be nice to rework things to match
    # while maintaining backwards compatibility.
    # https://www.rfc-editor.org/rfc/rfc1876.html

    VALIDATORS = [LocValueValidator('loc-value-rfc', sets={'legacy', 'strict'})]

    @classmethod
    def _schema(cls):
        return {
            'type': 'object',
            'required': [
                'lat_degrees',
                'lat_minutes',
                'lat_seconds',
                'lat_direction',
                'long_degrees',
                'long_minutes',
                'long_seconds',
                'long_direction',
                'altitude',
                'size',
                'precision_horz',
                'precision_vert',
            ],
            'properties': {
                'lat_degrees': {'type': 'integer', 'minimum': 0, 'maximum': 90},
                'lat_minutes': {'type': 'integer', 'minimum': 0, 'maximum': 59},
                'lat_seconds': {
                    'type': 'number',
                    'minimum': 0,
                    'maximum': 59.999,
                },
                'lat_direction': {'enum': ['N', 'S']},
                'long_degrees': {
                    'type': 'integer',
                    'minimum': 0,
                    'maximum': 180,
                },
                'long_minutes': {
                    'type': 'integer',
                    'minimum': 0,
                    'maximum': 59,
                },
                'long_seconds': {
                    'type': 'number',
                    'minimum': 0,
                    'maximum': 59.999,
                },
                'long_direction': {'enum': ['E', 'W']},
                'altitude': {
                    'type': 'number',
                    'minimum': -100000.00,
                    'maximum': 42849672.95,
                },
                'size': {
                    'type': 'number',
                    'minimum': 0,
                    'maximum': 90000000.00,
                },
                'precision_horz': {
                    'type': 'number',
                    'minimum': 0,
                    'maximum': 90000000.00,
                },
                'precision_vert': {
                    'type': 'number',
                    'minimum': 0,
                    'maximum': 90000000.00,
                },
            },
        }

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
            altitude = float(unquote(altitude))
        except ValueError:
            pass
        try:
            size = float(unquote(size))
        except ValueError:
            pass
        try:
            precision_horz = float(unquote(precision_horz))
        except ValueError:
            pass
        try:
            precision_vert = float(unquote(precision_vert))
        except ValueError:
            pass
        lat_direction = unquote(lat_direction)
        long_direction = unquote(long_direction)
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

    def template(self, params):
        return self

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
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc1876',)
    _type = 'LOC'
    _value_type = LocValue


Record.register_type(LocRecord)
