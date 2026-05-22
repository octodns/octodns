#
#
#

from ipaddress import IPv4Address as _IPv4Address
from typing import ClassVar, Type

from .base import Record
from .dynamic import _DynamicMixin
from .geo import _GeoMixin
from .ip import _IpValue


class Ipv4Value(_IpValue):
    _address_type: Type[_IPv4Address] = _IPv4Address  # type: ignore[misc]
    _address_name: str = 'IPv4'


Ipv4Address = Ipv4Value


class ARecord(_DynamicMixin, _GeoMixin, Record):
    REFERENCES: tuple[str, ...] = (
        'https://datatracker.ietf.org/doc/html/rfc1035',
    )
    _type: ClassVar[str] = 'A'
    _value_type: ClassVar[Type[Ipv4Value]] = Ipv4Value  # type: ignore[misc]


Record.register_type(ARecord)
