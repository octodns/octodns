#
#
#

from .base import Zone
from .validator import ValidationReason, ZoneValidator


class CnameCoexistenceValidator(ZoneValidator):
    '''
    Verify that CNAME records do not coexist with other records at the same
    node.
    '''

    def validate(self, zone: 'Zone') -> list['ValidationReason']:
        reasons: list['ValidationReason'] = []
        for node in zone._records.values():
            if len(node) > 1:
                types = [r._type for r in node]  # type: ignore[attr-defined]
                if 'CNAME' in types:
                    # All records at this node have the same FQDN
                    record = next(iter(node))
                    reasons.append(
                        ValidationReason(
                            f'Invalid state, CNAME at {record.fqdn} cannot coexist with other records',
                            node,
                        )
                    )

        return reasons


Zone.register_zone_validator(
    CnameCoexistenceValidator('cname-coexistence', sets={'legacy', 'strict'})
)
