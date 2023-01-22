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
    _type = 'AAAA'
    _value_type = Ipv6Address


Record.register_type(AaaaRecord)
