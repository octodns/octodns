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
                                    f'NS record "{record.fqdn}" points to '
                                    f'in-zone target "{target}" without '
                                    'glue records (A/AAAA)',
                                    [record],
                                )
                            )
        return reasons


class MultiValueApexNsZoneValidator(ZoneValidator):
    '''
    Checks that the zone apex has at least two ``NS`` records. Having multiple
    name servers is a fundamental best practice for DNS redundancy and
    availability.
    '''

    def validate(self, zone):
        ns_records = zone.get('', type='NS')
        if ns_records:
            count = sum(len(r.values) for r in ns_records)
            if count < 2:
                return [
                    ValidationReason(
                        f'zone "{zone.decoded_name}" has only {count} NS '
                        'record at the apex; at least 2 are recommended for '
                        'redundancy',
                        list(ns_records),
                    )
                ]
        return []


Zone.register_zone_validator(
    GlueForInZoneNsZoneValidator('glue-for-in-zone-ns', sets={'strict'})
)
Zone.register_zone_validator(
    MultiValueApexNsZoneValidator('multi-value-apex-ns', sets={'best-practice'})
)
