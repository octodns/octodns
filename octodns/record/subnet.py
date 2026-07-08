#
#
#

import ipaddress

from .validator import ValidationReason


class Subnets(object):
    @classmethod
    def validate(cls, subnet, prefix, validator_id=None):
        '''
        Validates an octoDNS subnet making sure that it is valid
        '''
        reasons = []

        try:
            cls.parse(subnet)
        except ValueError:
            reasons.append(
                ValidationReason(
                    f'{prefix}invalid subnet "{subnet}"',
                    validator_id=validator_id,
                )
            )

        return reasons

    @classmethod
    def parse(cls, subnet):
        return ipaddress.ip_network(subnet)
