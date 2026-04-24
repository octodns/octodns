#
#
#

from ipaddress import IPv6Address as _IPv6Address

from .base import Record
from .dynamic import _DynamicMixin
from .geo import _GeoMixin
from .ip import _IpValue


class Ipv6Value(_IpValue):
    _address_type = _IPv6Address
    _address_name = 'IPv6'


Ipv6Address = Ipv6Value


class AaaaRecord(_DynamicMixin, _GeoMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc3596',)
    _type = 'AAAA'
    _value_type = Ipv6Address


Record.register_type(AaaaRecord)
Record.register_validator(_GeoMixin.VALIDATOR, types=['AAAA'])
Record.register_validator(_DynamicMixin.VALIDATOR, types=['AAAA'])
Record.register_validator(Ipv6Value.VALIDATOR, types=['AAAA'])
