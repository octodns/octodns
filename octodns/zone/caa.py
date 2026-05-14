#
#
#

from .base import Zone
from .validator import ValidationReason, ZoneValidator


class ApexCaaPresenceZoneValidator(ZoneValidator):
    '''
    Checks that the zone apex has at least one ``CAA`` record. ``CAA``
    (Certificate Authority Authorization) records allow domain owners to
    restrict which Certificate Authorities are allowed to issue certificates for
    their domain, improving security.

    Reference: https://datatracker.ietf.org/doc/html/rfc8659
    '''

    def validate(self, zone):
        caa_records = zone.get('', type='CAA')
        if not caa_records:
            return [
                ValidationReason(
                    f'zone "{zone.decoded_name}" has no CAA records at the apex',
                    set(),
                )
            ]
        return []


Zone.register_zone_validator(
    ApexCaaPresenceZoneValidator('apex-caa-presence', sets={'best-practice'})
)
