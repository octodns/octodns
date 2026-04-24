#
#
#

from ipaddress import IPv4Address as _IPv4Address

from .base import Record
from .dynamic import DynamicValidator, _DynamicMixin
from .geo import GeoValidator, _GeoMixin
from .ip import IpValueValidator, _IpValue


class Ipv4Value(_IpValue):
    _address_type = _IPv4Address
    _address_name = 'IPv4'


Ipv4Address = Ipv4Value


class ARecord(_DynamicMixin, _GeoMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc1035',)
    _type = 'A'
    _value_type = Ipv4Value


Record.register_type(ARecord)
Record.register_validator(GeoValidator('geo'), types=['A'])
Record.register_validator(DynamicValidator('dynamic'), types=['A'])
Record.register_validator(IpValueValidator('ip-value'), types=['A'])
