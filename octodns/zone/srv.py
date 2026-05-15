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
                                    f'SRV record "{record.fqdn}" points to target "{target}" which is a CNAME',
                                    [record],
                                )
                            )
        return reasons


Zone.register_zone_validator(
    SrvTargetNotCnameZoneValidator('srv-target-not-cname', sets={'strict'})
)
