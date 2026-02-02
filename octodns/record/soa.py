#
#
#


from fqdn import FQDN

from ..equality import EqualityTupleMixin
from .base import Record, ValueMixin
from .rr import RrParseError


class SoaValue(EqualityTupleMixin, dict):
    @classmethod
    def parse_rdata_text(cls, value):
        try:
            mname, rname, serial, refresh, retry, expire, minimum = value.split(
                ' '
            )
        except ValueError as ve:
            raise RrParseError('Failed to split SOA rdata value: ' + str(ve))
        if not FQDN(mname).is_valid:
            raise RrParseError(f'Failed to parse mname {mname} as FQDN')
        if not FQDN(rname).is_valid:
            raise RrParseError(f'Failed to parse rname {rname} as FQDN')
        try:
            serial = int(serial)
        except ValueError as ve:
            raise RrParseError('Failed to parse serial: ' + str(ve))
        try:
            refresh = int(refresh)
        except ValueError as ve:
            raise RrParseError('Failed to parse refresh: ' + str(ve))
        try:
            retry = int(retry)
        except ValueError as ve:
            raise RrParseError('Failed to parse retry: ' + str(ve))
        try:
            expire = int(expire)
        except ValueError as ve:
            raise RrParseError('Failed to parse expire: ' + str(ve))
        try:
            minimum = int(minimum)
        except ValueError as ve:
            raise RrParseError('Failed to parse minimum: ' + str(ve))
        return {
            'mname': mname,
            'rname': rname,
            'serial': serial,
            'refresh': refresh,
            'retry': retry,
            'expire': expire,
            'minimum': minimum,
        }

    @classmethod
    def validate(cls, data, _type):
        reasons = []
        try:
            if not FQDN(data['mname']).is_valid:
                reasons.append('invalid mname')
        except KeyError:
            reasons.append('missing mname')
        try:
            if not FQDN(data['rname']).is_valid:
                reasons.append('invalid rname')
        except KeyError:
            reasons.append('missing rname')
        try:
            int(data['serial'])
        except KeyError:
            reasons.append('missing serial')
        except ValueError:
            reasons.append('invalid serial')
        try:
            int(data['refresh'])
        except KeyError:
            reasons.append('missing refresh')
        except ValueError:
            reasons.append('invalid refresh value')
        try:
            int(data['retry'])
        except KeyError:
            reasons.append('missing retry')
        except ValueError:
            reasons.append('invalid retry value')
        try:
            int(data['expire'])
        except KeyError:
            reasons.append('missing expire')
        except ValueError:
            reasons.append('invalid expire value')
        try:
            int(data['minimum'])
        except KeyError:
            reasons.append('missing minimum')
        except ValueError:
            reasons.append('invalid minimum value')

        return reasons

    @classmethod
    def process(cls, value):
        return cls(value)

    def __init__(self, value):
        super().__init__(
            {
                'mname': str(value['mname']),
                'rname': str(value['rname']),
                'serial': int(value['serial']),
                'refresh': int(value['refresh']),
                'retry': int(value['retry']),
                'expire': int(value['expire']),
                'minimum': int(value['minimum']),
            }
        )

    @property
    def mname(self):
        return self['mname']

    @mname.setter
    def mname(self, value):
        self['mname'] = value

    @property
    def rname(self):
        return self['rname']

    @rname.setter
    def rname(self, value):
        self['rname'] = value

    @property
    def serial(self):
        return self['serial']

    @serial.setter
    def serial(self, value):
        self['serial'] = value

    @property
    def refresh(self):
        return self['refresh']

    @refresh.setter
    def refresh(self, value):
        self['refresh'] = value

    @property
    def retry(self):
        return self['retry']

    @retry.setter
    def retry(self, value):
        self['retry'] = value

    @property
    def expire(self):
        return self['expire']

    @expire.setter
    def expire(self, value):
        self['expire'] = value

    @property
    def minimum(self):
        return self['minimum']

    @minimum.setter
    def minimum(self, value):
        self['minimum'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return f"{self.mname} {self.rname} {self.serial} {self.refresh} {self.retry} {self.expire} {self.minimum}"

    def template(self, params):
        if '{' not in self.mname + self.rname:
            return self
        new = self.__class__(self)
        new.mname = new.mname.format(**params)
        new.rname = new.rname.format(**params)
        return new

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (
            self.mname,
            self.rname,
            self.serial,
            self.refresh,
            self.retry,
            self.expire,
            self.minimum,
        )

    def __repr__(self):
        return f"'{self.rdata_text}'"


class SoaRecord(ValueMixin, Record):
    _type = 'SOA'
    _value_type = SoaValue

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = []
        if name != '':
            reasons.append('non-root SOA not allowed')
        reasons.extend(super().validate(name, fqdn, data))
        return reasons


Record.register_type(SoaRecord)
