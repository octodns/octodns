#
#
#

import ipaddress
from logging import getLogger


class Subnets(object):
    log = getLogger('Subnets')

    @classmethod
    def validate(cls, subnet, prefix):
        '''
        Validates an octoDNS subnet making sure that it is valid
        '''
        reasons = []

        try:
            ipaddress.ip_network(subnet)
        except ValueError:
            reasons.append(f'{prefix}invalid subnet "{subnet}"')

        return reasons

    @classmethod
    def parse(cls, subnet):
        return ipaddress.ip_network(subnet)
