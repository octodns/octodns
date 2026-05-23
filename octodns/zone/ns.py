#
#
#

from .base import Zone
from .validator import ValidationReason, ZoneValidator


class GlueForInZoneNsZoneValidator(ZoneValidator):
    '''
    Checks that NS records pointing to targets within the same zone have
    corresponding A or AAAA "glue" records. Without these address records,
    resolvers cannot follow the delegation because they would need to resolve
    the name server's address using the very name servers they are trying to
    locate.

    Example:
      - Zone ``example.com.`` has ``NS ns1.example.com.``
      - This validator ensures an ``A`` or ``AAAA`` record exists for
        ``ns1.example.com.`` within the ``example.com.`` zone.

    Reference: https://datatracker.ietf.org/doc/html/rfc1033 (Operations)
    '''

    def validate(self, zone):
        reasons = []
        for record in zone.records:
            if record._type == 'NS':
                for target in record.values:
                    # Is target in zone?
                    if zone.owns('A', target):
                        # Check if address records exist at this target
                        hostname = zone.hostname_from_fqdn(target)
                        # We need at least one A or AAAA
                        addresses = zone.get(hostname, type='A') | zone.get(
                            hostname, type='AAAA'
                        )
                        if not addresses:
                            reasons.append(
                                ValidationReason(
                                    f'NS record "{record.fqdn}" points to in-zone target "{target}" without glue records (A/AAAA)',
                                    [record],
                                )
                            )
        return reasons


class NsTargetNotCnameZoneValidator(ZoneValidator):
    '''
    Checks that NS records do not point to targets that are CNAMEs within the
    same zone. A CNAME target for NS is invalid because resolvers need the
    actual A/AAAA records to follow the delegation.
    '''

    def validate(self, zone):
        reasons = []
        for record in zone.records:
            if record._type == 'NS':
                for target in record.values:
                    if zone.owns('CNAME', target):
                        hostname = zone.hostname_from_fqdn(target)
                        cnames = zone.get(hostname, type='CNAME')
                        if cnames:
                            reasons.append(
                                ValidationReason(
                                    f'NS record "{record.fqdn}" points to target "{target}" which is a CNAME',
                                    [record],
                                )
                            )
        return reasons


class MultiValueNsZoneValidator(ZoneValidator):
    '''
    Checks that all ``NS`` records have at least two values. Having multiple
    name servers is a fundamental best practice for DNS redundancy and
    availability, both at the apex and for sub-delegations.
    '''

    def validate(self, zone):
        reasons = []
        for record in zone.records:
            if record._type == 'NS':
                if len(record.values) < 2:
                    reasons.append(
                        ValidationReason(
                            f'NS record "{record.fqdn}" has only {len(record.values)} value; at least 2 are recommended for redundancy',
                            [record],
                        )
                    )
        return reasons


Zone.register_zone_validator(
    GlueForInZoneNsZoneValidator('glue-for-in-zone-ns', sets={'strict'})
)
Zone.register_zone_validator(
    MultiValueNsZoneValidator('multi-value-ns', sets={'best-practice'})
)
Zone.register_zone_validator(
    NsTargetNotCnameZoneValidator('ns-target-not-cname', sets={'strict'})
)
