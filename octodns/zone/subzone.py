#
#
#

from .base import Zone
from .validator import ValidationReason, ZoneValidator


class SubzoneRecordValidator(ZoneValidator):
    '''
    Verify that records do not overlap with managed sub-zones.
    '''

    def validate(self, zone: 'Zone') -> list['ValidationReason']:
        reasons: list['ValidationReason'] = []
        for record in zone.records:
            name = record.name
            if name in zone.sub_zones:
                if record._type not in ('NS', 'DS'):  # type: ignore[attr-defined]
                    reasons.append(
                        ValidationReason(
                            f'Record {record.fqdn} is a managed sub-zone and not of type NS or DS',
                            [record],
                        )
                    )
            else:
                for sub_zone in zone.sub_zones:
                    if name.endswith(f'.{sub_zone}'):
                        reasons.append(
                            ValidationReason(
                                f'Record {record.fqdn} is under a managed subzone',
                                [record],
                            )
                        )
                        break

        return reasons


Zone.register_zone_validator(
    SubzoneRecordValidator('subzone-record', sets={'legacy', 'strict'})
)
