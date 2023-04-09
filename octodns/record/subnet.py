#
#
#

import ipaddress


class Subnets(object):
    @classmethod
    def validate(cls, subnet, prefix):
        '''
        Validates an octoDNS subnet making sure that it is valid
        '''
        reasons = []

        try:
            cls.parse(subnet)
        except ValueError:
            reasons.append(f'{prefix}invalid subnet "{subnet}"')

        return reasons

    @classmethod
    def parse(cls, subnet):
        return ipaddress.ip_network(subnet)
