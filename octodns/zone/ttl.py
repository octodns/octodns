#
#
#

from .base import Zone
from .validator import ValidationReason, ZoneValidator


class ConsistentTtlAtNameZoneValidator(ZoneValidator):
    '''
    Verify that all records at the same name (node) share the same TTL.
    '''

    def validate(self, zone):
        reasons = []
        for node in zone._records.values():
            if len(node) > 1:
                ttls = {r.ttl for r in node}
                if len(ttls) > 1:
                    record = next(iter(node))
                    reasons.append(
                        ValidationReason(
                            f'Invalid state, multiple TTLs at {record.fqdn}',
                            node,
                        )
                    )
        return reasons


Zone.register_zone_validator(
    ConsistentTtlAtNameZoneValidator('consistent-ttl-at-name', sets={'strict'})
)
