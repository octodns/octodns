#
#
#

from ipaddress import IPv4Address as _IPv4Address

from .base import Record
from .dynamic import _DynamicMixin
from .geo import _GeoMixin
from .ip import _IpValue


class Ipv4Value(_IpValue):
    _address_type = _IPv4Address
    _address_name = 'IPv4'


Ipv4Address = Ipv4Value


class ARecord(_DynamicMixin, _GeoMixin, Record):
    _type = 'A'
    _value_type = Ipv4Value


Record.register_type(ARecord)
