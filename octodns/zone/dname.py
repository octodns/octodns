#
#
#

from .base import Zone
from .validator import ValidationReason, ZoneValidator


class DnameCoexistenceValidator(ZoneValidator):
    '''
    Verify that DNAME records do not coexist with CNAME records at any node,
    or with NS records at a non-apex node. Warn about records occluded by DNAME
    records.
    '''

    def validate(self, zone):
        reasons = []
        dnames = []

        for node in zone._records.values():
            types = [r._type for r in node]
            if 'DNAME' in types:
                dname_record = next(r for r in node if r._type == 'DNAME')
                dnames.append(dname_record)

                if 'CNAME' in types:
                    reasons.append(
                        ValidationReason(
                            f'Invalid state, DNAME at {dname_record.fqdn} cannot coexist with CNAME',
                            node,
                            validator_id=self.id,
                        )
                    )

                if 'NS' in types and dname_record.name != '':
                    reasons.append(
                        ValidationReason(
                            f'Invalid state, DNAME at {dname_record.fqdn} cannot coexist with NS at a non-apex node',
                            node,
                            validator_id=self.id,
                        )
                    )

        for dname in dnames:
            parent = dname.name
            for record in zone.records:
                name = record.name
                is_child = (
                    name != '' if parent == '' else name.endswith(f'.{parent}')
                )
                if is_child:
                    reasons.append(
                        ValidationReason(
                            f'Record "{record.decoded_fqdn}" is occluded by DNAME "{dname.decoded_fqdn}"',
                            [record],
                            validator_id=self.id,
                        )
                    )

        return reasons


Zone.register_zone_validator(
    DnameCoexistenceValidator('dname-coexistence', sets={'strict'})
)
