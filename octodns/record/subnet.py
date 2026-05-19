#
#
#
#

from __future__ import annotations

import ipaddress
from typing import Any


class Subnets(object):
    @classmethod
    def validate(cls, subnet: str, prefix: str) -> list[str]:
        '''
        Validates an octoDNS subnet making sure that it is valid
        '''
        reasons: list[str] = []

        try:
            cls.parse(subnet)
        except ValueError:
            reasons.append(f'{prefix}invalid subnet "{subnet}"')

        return reasons

    @classmethod
    def parse(cls, subnet: str) -> Any:
        return ipaddress.ip_network(subnet)
