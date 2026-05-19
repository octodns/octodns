#
#
#

from ipaddress import IPv6Address as _IPv6Address
from typing import ClassVar, Type

from .base import Record
from .dynamic import _DynamicMixin
from .geo import _GeoMixin
from .ip import _IpValue


class Ipv6Value(_IpValue):
    _address_type: Type[_IPv6Address] = _IPv6Address  # type: ignore[misc]
    _address_name: str = 'IPv6'


Ipv6Address = Ipv6Value


class AaaaRecord(_DynamicMixin, _GeoMixin, Record):
    REFERENCES: tuple[str, ...] = (
        'https://datatracker.ietf.org/doc/html/rfc3596',
    )
    _type: ClassVar[str] = 'AAAA'
    _value_type: ClassVar[Type[Ipv6Value]] = Ipv6Address  # type: ignore[misc]


Record.register_type(AaaaRecord)
