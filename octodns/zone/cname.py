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

    def validate(self, zone):
        reasons = []
        for node in zone._records.values():
            if len(node) > 1:
                types = [r._type for r in node]
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


class NoCnameLoopZoneValidator(ZoneValidator):
    '''
    Checks for circular CNAME or ALIAS chains within the zone. Circular
    references prevent DNS resolution from ever completing and are prohibited
    by DNS standards.

    Reference: https://datatracker.ietf.org/doc/html/rfc1034#section-3.6.2
    '''

    def validate(self, zone):
        reasons = []
        targets = {
            r.fqdn: r for r in zone.records if r._type in ('CNAME', 'ALIAS')
        }

        overall_visited = set()
        for start_fqdn in targets:
            if start_fqdn in overall_visited:
                continue

            path = []
            visited = {}  # fqdn -> index in path
            curr = start_fqdn

            while curr in targets:
                if curr in visited:
                    cycle_fqdns = path[visited[curr] :] + [curr]
                    loop_path = ' -> '.join(cycle_fqdns)
                    cycle_records = {
                        targets[f] for f in cycle_fqdns if f in targets
                    }
                    reasons.append(
                        ValidationReason(
                            f'Loop detected: {loop_path}', cycle_records
                        )
                    )
                    break

                if curr in overall_visited:
                    break

                visited[curr] = len(path)
                path.append(curr)
                overall_visited.add(curr)
                curr = str(targets[curr].value)

        return reasons


class CnameTargetResolvableInZoneZoneValidator(ZoneValidator):
    '''
    Checks that ``CNAME`` and ``ALIAS`` records pointing to targets within the
    same zone have a corresponding record at that target. This helps detect
    "dangling" references that can occur after refactors or deletions.
    '''

    def validate(self, zone):
        reasons = []
        for record in zone.records:
            if record._type in ('CNAME', 'ALIAS'):
                target = str(record.value)
                if zone.owns('A', target):
                    hostname = zone.hostname_from_fqdn(target)
                    if not zone.get(hostname):
                        reasons.append(
                            ValidationReason(
                                f'{record._type} record "{record.decoded_fqdn}" points to in-zone target "{target}" that does not exist',
                                [record],
                            )
                        )
        return reasons


Zone.register_zone_validator(
    CnameCoexistenceValidator('cname-coexistence', sets={'legacy', 'strict'})
)

Zone.register_zone_validator(
    NoCnameLoopZoneValidator('no-cname-loop', sets={'strict'})
)

Zone.register_zone_validator(
    CnameTargetResolvableInZoneZoneValidator(
        'cname-target-resolvable-in-zone', sets={'best-practice'}
    )
)
