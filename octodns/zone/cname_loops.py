#
#
#

from .base import Zone
from .validator import ValidationReason, ZoneValidator


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


Zone.register_zone_validator(
    NoCnameLoopZoneValidator('no-cname-loop', sets={'strict'})
)
