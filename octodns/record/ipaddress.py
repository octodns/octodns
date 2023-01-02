#
#
#

from ipaddress import IPv4Address as _IPv4Address, IPv6Address as _IPv6Address

from .base import Record
from .dynamic import _DynamicMixin
from .geo import _GeoMixin


class _IpAddress(str):
    @classmethod
    def parse_rdata_text(cls, value):
        return value

    @classmethod
    def validate(cls, data, _type):
        if not isinstance(data, (list, tuple)):
            data = (data,)
        if len(data) == 0:
            return ['missing value(s)']
        reasons = []
        for value in data:
            if value == '':
                reasons.append('empty value')
            elif value is None:
                reasons.append('missing value(s)')
            else:
                try:
                    cls._address_type(str(value))
                except Exception:
                    addr_name = cls._address_name
                    reasons.append(f'invalid {addr_name} address "{value}"')
        return reasons

    @classmethod
    def process(cls, values):
        # Translating None into '' so that the list will be sortable in
        # python3, get everything to str first
        values = [v if v is not None else '' for v in values]
        # Now round trip all non-'' through the address type and back to a str
        # to normalize the address representation.
        return [cls(v) if v != '' else '' for v in values]

    def __new__(cls, v):
        v = str(cls._address_type(v))
        return super().__new__(cls, v)

    @property
    def rdata_text(self):
        return self


class Ipv4Address(_IpAddress):
    _address_type = _IPv4Address
    _address_name = 'IPv4'


class ARecord(_DynamicMixin, _GeoMixin, Record):
    _type = 'A'
    _value_type = Ipv4Address


Record.register_type(ARecord)


class Ipv6Address(_IpAddress):
    _address_type = _IPv6Address
    _address_name = 'IPv6'


class AaaaRecord(_DynamicMixin, _GeoMixin, Record):
    _type = 'AAAA'
    _value_type = Ipv6Address


Record.register_type(AaaaRecord)
