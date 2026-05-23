#
#
#

from .base import Zone
from .validator import ValidationReason, ZoneValidator


class SrvTargetNotCnameZoneValidator(ZoneValidator):
    '''
    Checks that SRV records do not point to targets that are CNAMEs within the
    same zone. Per RFC 2782, the SRV target must be an A/AAAA record, not a
    CNAME.
    '''

    def validate(self, zone):
        reasons = []
        for record in zone.records:
            if record._type == 'SRV':
                for value in record.values:
                    target = value.target
                    if target == '.':
                        continue
                    if zone.owns('CNAME', target):
                        hostname = zone.hostname_from_fqdn(target)
                        cnames = zone.get(hostname, type='CNAME')
                        if cnames:
                            reasons.append(
                                ValidationReason(
                                    f'SRV record "{record.decoded_fqdn}" points to target "{target}" which is a CNAME',
                                    [record],
                                )
                            )
        return reasons


class SrvTargetResolvableInZoneZoneValidator(ZoneValidator):
    '''
    Checks that ``SRV`` targets pointing to targets within the same zone have
    corresponding address records.
    '''

    def validate(self, zone):
        reasons = []
        for record in zone.records:
            if record._type == 'SRV':
                for value in record.values:
                    target = value.target
                    if zone.owns('A', target):
                        hostname = zone.hostname_from_fqdn(target)
                        if not zone.get(hostname):
                            reasons.append(
                                ValidationReason(
                                    f'SRV record "{record.decoded_fqdn}" points to in-zone target "{target}" that does not exist',
                                    [record],
                                )
                            )
        return reasons


Zone.register_zone_validator(
    SrvTargetNotCnameZoneValidator('srv-target-not-cname', sets={'strict'})
)

Zone.register_zone_validator(
    SrvTargetResolvableInZoneZoneValidator(
        'srv-target-resolvable-in-zone', sets={'best-practice'}
    )
)
