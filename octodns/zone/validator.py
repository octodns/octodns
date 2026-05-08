#
#
#

from logging import getLogger

from .exception import ZoneException


class ZoneValidatorRegistry:
    log = getLogger('Zone')

    def __init__(self):
        self.available = {}
        self.active = {}
        self.configured = False

    def register(self, validator):
        if not isinstance(validator, ZoneValidator):
            raise ZoneException(
                f'{validator.__class__.__name__} must be a ZoneValidator instance'
            )
        if validator.id in self.available:
            raise ZoneException(
                f'ZoneValidator id "{validator.id}" already registered'
            )
        self.available[validator.id] = validator

    def enable_sets(self, sets):
        self.configured = True
        self.active.clear()
        sets = set(sets)
        for validator in self.available.values():
            if validator.sets is None or sets & validator.sets:
                self.active[validator.id] = validator

    def enable(self, id):
        if id not in self.available:
            raise ZoneException(f'Unknown zone validator id "{id}"')
        self.active[id] = self.available[id]

    def disable(self, validator_id):
        if validator_id.startswith('_'):
            raise ZoneException(
                f'Cannot disable bridge zone validator "{validator_id}"'
            )
        return self.active.pop(validator_id, None) is not None

    def reset_active(self):
        self.active.clear()

    def registered(self):
        return list(self.active.values())

    def available_validators(self):
        return list(self.available.values())

    def process_zone(self, zone):
        if not self.configured:
            self.log.warning(
                'process_zone: no zone validators configured, automatically enabling legacy set'
            )
            self.enable_sets({'legacy'})
        reasons = []
        for validator in self.active.values():
            reasons.extend(validator.validate(zone))
        return reasons


class ZoneValidator:
    '''
    Base class for zone-level validators.

    Subclasses override ``validate`` to return a list of reason strings
    describing any validation failures. An empty list indicates the zone is
    valid. The zone validator receives the fully assembled desired Zone and
    may examine any records within it. Because zone validators see the whole
    zone at once, they are suited for cross-record checks (e.g. requiring at
    least two MX values at the apex) that per-record validators cannot perform.

    Every zone validator instance has a non-empty ``id`` — a short, stable,
    kebab-case identifier (e.g. ``'multi-value-mx'``). Config-registered
    validators receive their config key as ``id`` automatically.
    '''

    def __init__(self, id, sets=None):
        '''
        :param id: Non-empty identifier for this validator instance.
        :param sets: Iterable of set names, or ``None`` to always activate.
        '''
        if not id:
            raise ValueError(
                f'{self.__class__.__name__} requires a non-empty id'
            )
        self.id = id
        self.sets = set(sets) if sets is not None else None

    def validate(self, zone):
        '''
        Validate a fully populated zone.

        :param zone: The Zone to validate.
        :returns: list[str] of reason strings; empty when valid.
        '''
        return []


class MultiValueMxZoneValidator(ZoneValidator):
    '''
    Checks that every MX record in the zone has at least two values.
    Single-value MX records are technically valid but are not recommended
    in production zones as they create a single point of failure.
    '''

    def validate(self, zone):
        reasons = []
        for record in zone.records:
            if record._type == 'MX' and len(record.values) < 2:
                reasons.append(
                    f'MX record "{record.fqdn}" should have at least 2 values'
                    f' for redundancy, found {len(record.values)}'
                )
        return reasons


class ApexSpfPresenceZoneValidator(ZoneValidator):
    '''
    Checks that the zone apex has at least one TXT record whose value begins
    with ``v=spf1``, indicating an SPF policy is published. Publishing SPF
    records helps prevent email spoofing of the domain.

    For domains that do not send email, it is recommended to publish a
    restrictive policy: ``v=spf1 -all``.
    '''

    def validate(self, zone):
        apex_txts = zone.get('', type='TXT')
        if not apex_txts:
            return [
                f'zone "{zone.decoded_name}" has no TXT records at the apex;'
                ' add an SPF record (v=spf1 ...)'
            ]
        for record in apex_txts:
            for value in record.values:
                if str(value).startswith('v=spf1'):
                    return []
        return [
            f'zone "{zone.decoded_name}" has no SPF TXT record at the apex'
            ' (no value starting with "v=spf1")'
        ]


class ApexDmarcPresenceZoneValidator(ZoneValidator):
    '''
    Checks that the zone has a TXT record at the ``_dmarc`` hostname whose value
    begins with ``v=DMARC1``, indicating a DMARC policy is published. DMARC
    (Domain-based Message Authentication, Reporting, and Conformance) allows
    domain owners to specify how receivers should handle emails that fail SPF or
    DKIM checks.

    Common examples:
      - Monitoring: ``v=DMARC1; p=none; rua=mailto:dmarc@example.com``
      - Enforcement: ``v=DMARC1; p=reject; rua=mailto:dmarc@example.com``
      - No-email domains: ``v=DMARC1; p=reject;``

    Reference: https://datatracker.ietf.org/doc/html/rfc7489
    '''

    def validate(self, zone):
        dmarc_txts = zone.get('_dmarc', type='TXT')
        if not dmarc_txts:
            return [
                f'zone "{zone.decoded_name}" has no TXT records at "_dmarc";'
                ' add a DMARC record (v=DMARC1 ...)'
            ]
        for record in dmarc_txts:
            for value in record.values:
                if str(value).startswith('v=DMARC1'):
                    return []
        return [
            f'zone "{zone.decoded_name}" has no DMARC TXT record at "_dmarc"'
            ' (no value starting with "v=DMARC1")'
        ]


class NoCnameLoopZoneValidator(ZoneValidator):
    '''
    Checks for circular CNAME or ALIAS chains within the zone. Circular
    references prevent DNS resolution from ever completing and are prohibited
    by DNS standards.

    Example of a loop:
      - ``www.example.com. CNAME lb.example.com.``
      - ``lb.example.com.  CNAME www.example.com.``

    Reference: https://datatracker.ietf.org/doc/html/rfc1034#section-3.6.2
    '''

    def validate(self, zone):
        reasons = []
        # ALIAS and CNAME both act as redirections that can loop
        targets = {
            r.fqdn: str(r.value)
            for r in zone.records
            if r._type in ('CNAME', 'ALIAS')
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
                    loop_path = ' -> '.join(path[visited[curr] :] + [curr])
                    reasons.append(f'Loop detected: {loop_path}')
                    break

                if curr in overall_visited:
                    # We already explored this path and didn't find a loop
                    break

                visited[curr] = len(path)
                path.append(curr)
                overall_visited.add(curr)
                curr = targets[curr]

        return reasons


class ConsistentTtlAtNameZoneValidator(ZoneValidator):
    '''
    Checks that all records at a specific name share the same TTL. Inconsistent
    TTLs for records at the same name can lead to cache skew.

    For example, if an ``A`` record has a TTL of 300s and an ``AAAA`` record at
    the same name has a TTL of 3600s, a resolver might cache the ``AAAA`` record
    long after the ``A`` record has expired (and potentially changed), leading
    to inconsistent resolution results for dual-stack clients.
    '''

    def validate(self, zone):
        reasons = []
        # zone._records is grouped by name
        for name, records in zone._records.items():
            if len(records) > 1:
                ttls = {r.ttl for r in records}
                if len(ttls) > 1:
                    fqdn = (
                        f'{name}.{zone.decoded_name}'
                        if name
                        else zone.decoded_name
                    )
                    reasons.append(
                        f'Inconsistent TTLs at "{fqdn}": found {sorted(ttls)}'
                    )
        return reasons


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
                                f'NS record "{record.fqdn}" points to '
                                f'in-zone target "{target}" without '
                                'glue records (A/AAAA)'
                            )
        return reasons


class SingleSpfZoneValidator(ZoneValidator):
    '''
    Checks that there is at most one SPF record at the zone apex. Multiple SPF
    records are a configuration error and will cause a "PermError", invalidating
    all SPF policies for the domain.

    Example:
      - Hostname ``unit.tests.`` has two ``TXT`` records starting with ``v=spf1``.

    Reference: https://datatracker.ietf.org/doc/html/rfc7208#section-3.2
    '''

    def validate(self, zone):
        apex_txts = zone.get('', type='TXT')
        spf_count = 0
        for record in apex_txts:
            for value in record.values:
                if str(value).startswith('v=spf1'):
                    spf_count += 1

        if spf_count > 1:
            return [
                f'zone "{zone.decoded_name}" has {spf_count} SPF records; '
                'only one is allowed'
            ]
        return []


class NoSelfReferencingTargetZoneValidator(ZoneValidator):
    '''
    Checks for records that point to their own FQDN as a target. Such
    configurations are logically circular and can cause resolution failures.

    Applies to: ``ALIAS``, ``CNAME``, ``MX``, ``NS``, ``PTR``, and ``SRV``.
    '''

    def validate(self, zone):
        reasons = []
        for record in zone.records:
            _type = record._type
            if _type in ('ALIAS', 'CNAME', 'PTR'):
                if str(record.value) == record.fqdn:
                    reasons.append(
                        f'{_type} record "{record.fqdn}" points to itself'
                    )
            if _type == 'MX':
                for value in record.values:
                    if value.exchange == record.fqdn:
                        reasons.append(
                            f'MX record "{record.fqdn}" points to itself'
                        )
            if _type == 'NS':
                for target in record.values:
                    if str(target) == record.fqdn:
                        reasons.append(
                            f'NS record "{record.fqdn}" points to itself'
                        )
            if _type == 'SRV':
                for value in record.values:
                    if value.target == record.fqdn:
                        reasons.append(
                            f'SRV record "{record.fqdn}" points to itself'
                        )
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
                            f'{record._type} record "{record.fqdn}" points '
                            f'to in-zone target "{target}" that does '
                            'not exist'
                        )
        return reasons


class _TargetNotCnameZoneValidator(ZoneValidator):
    _types = ()

    def validate(self, zone):
        reasons = []
        for record in zone.records:
            if record._type in self._types:
                # We need to collect targets based on record type
                targets = []
                if record._type == 'MX':
                    targets = [v.exchange for v in record.values]
                if record._type == 'NS':
                    targets = record.values
                if record._type == 'SRV':
                    targets = [v.target for v in record.values]

                for target in targets:
                    if zone.owns('CNAME', target):
                        hostname = zone.hostname_from_fqdn(target)
                        if zone.get(hostname, type='CNAME'):
                            reasons.append(
                                f'{record._type} record "{record.fqdn}" '
                                f'points to in-zone target "{target}" '
                                'which is a CNAME'
                            )
        return reasons


class NsTargetNotCnameZoneValidator(_TargetNotCnameZoneValidator):
    '''
    Checks that ``NS`` records do not point to a ``CNAME``. This is prohibited
    by DNS standards and can cause resolution failures.

    Reference: https://datatracker.ietf.org/doc/html/rfc2181#section-10.3
    '''

    _types = ('NS',)


class MxTargetNotCnameZoneValidator(_TargetNotCnameZoneValidator):
    '''
    Checks that ``MX`` records do not point to a ``CNAME``. This is prohibited
    by DNS standards.

    Reference: https://datatracker.ietf.org/doc/html/rfc5321#section-5.1
    '''

    _types = ('MX',)


class SrvTargetNotCnameZoneValidator(_TargetNotCnameZoneValidator):
    '''
    Checks that ``SRV`` records do not point to a ``CNAME``. This is prohibited
    by DNS standards.

    Reference: https://datatracker.ietf.org/doc/html/rfc2782
    '''

    _types = ('SRV',)


class ApexNsPresenceZoneValidator(ZoneValidator):
    '''
    Checks that the zone apex has at least one ``NS`` record. Root ``NS``
    records are required for any functional DNS zone.

    Note: Some DNS providers manage the root ``NS`` records automatically and
    do not allow them to be configured in octoDNS. This validator should only
    be enabled for zones where the apex ``NS`` records are managed.

    Reference: https://datatracker.ietf.org/doc/html/rfc1034
    '''

    def validate(self, zone):
        if not zone.get('', type='NS'):
            return [
                f'zone "{zone.decoded_name}" is missing NS records at the apex'
            ]
        return []


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
                    f'zone "{zone.decoded_name}" has only {count} NS '
                    'record at the apex; at least 2 are recommended for '
                    'redundancy'
                ]
        return []


class OverlappingSubzoneZoneValidator(ZoneValidator):
    '''
    Checks for records that exist "below" a delegation boundary (an ``NS``
    record) within the same zone. Such records are shadowed by the delegation
    and will never be reached by DNS resolvers, often indicating a
    configuration error or stale data.

    Example:
      - Zone ``example.com.`` has ``NS sub.example.com.``
      - A record at ``www.sub.example.com.`` within this zone is shadowed.
    '''

    def validate(self, zone):
        reasons = []
        # Find all delegations (NS records not at the apex)
        delegations = [
            r.fqdn for r in zone.records if r._type == 'NS' and r.name
        ]

        for record in zone.records:
            for delegation in delegations:
                # Is record.fqdn a subdomain of delegation?
                if record.fqdn.endswith(f'.{delegation}'):
                    reasons.append(
                        f'Record "{record.fqdn}" is shadowed by '
                        f'delegation at "{delegation}"'
                    )
        return reasons


class ApexCaaPresenceZoneValidator(ZoneValidator):
    '''
    Checks that the zone apex has at least one ``CAA`` record. ``CAA``
    (Certificate Authority Authorization) records allow domain owners to
    restrict which Certificate Authorities are allowed to issue certificates for
    their domain, improving security.

    Reference: https://datatracker.ietf.org/doc/html/rfc8659
    '''

    def validate(self, zone):
        if not zone.get('', type='CAA'):
            return [
                f'zone "{zone.decoded_name}" has no CAA records at the apex'
            ]
        return []


class _TargetResolvableInZoneZoneValidator(ZoneValidator):
    _types = ()

    def validate(self, zone):
        reasons = []
        for record in zone.records:
            if record._type in self._types:
                targets = []
                if record._type == 'MX':
                    targets = [v.exchange for v in record.values]
                if record._type == 'SRV':
                    targets = [v.target for v in record.values]

                for target in targets:
                    if zone.owns('A', target):
                        hostname = zone.hostname_from_fqdn(target)
                        if not zone.get(hostname):
                            reasons.append(
                                f'{record._type} record "{record.fqdn}" '
                                f'points to in-zone target "{target}" '
                                'that does not exist'
                            )
        return reasons


class MxTargetResolvableInZoneZoneValidator(
    _TargetResolvableInZoneZoneValidator
):
    '''
    Checks that ``MX`` exchanges pointing to targets within the same zone have
    corresponding address records.
    '''

    _types = ('MX',)


class SrvTargetResolvableInZoneZoneValidator(
    _TargetResolvableInZoneZoneValidator
):
    '''
    Checks that ``SRV`` targets pointing to targets within the same zone have
    corresponding address records.
    '''

    _types = ('SRV',)


zone_validators = ZoneValidatorRegistry()
zone_validators.register(
    MultiValueMxZoneValidator('multi-value-mx', sets={'best-practice'})
)
zone_validators.register(
    ApexSpfPresenceZoneValidator('apex-spf-presence', sets={'best-practice'})
)
zone_validators.register(
    ApexDmarcPresenceZoneValidator(
        'apex-dmarc-presence', sets={'best-practice'}
    )
)
zone_validators.register(
    NoCnameLoopZoneValidator('no-cname-loop', sets={'strict'})
)
zone_validators.register(
    ConsistentTtlAtNameZoneValidator(
        'consistent-ttl-at-name', sets={'best-practice'}
    )
)
zone_validators.register(
    GlueForInZoneNsZoneValidator('glue-for-in-zone-ns', sets={'strict'})
)
zone_validators.register(SingleSpfZoneValidator('single-spf', sets={'strict'}))
zone_validators.register(
    NoSelfReferencingTargetZoneValidator(
        'no-self-referencing-target', sets={'strict'}
    )
)
zone_validators.register(
    CnameTargetResolvableInZoneZoneValidator(
        'cname-target-resolvable-in-zone', sets={'best-practice'}
    )
)
zone_validators.register(
    NsTargetNotCnameZoneValidator('ns-target-not-cname', sets={'strict'})
)
zone_validators.register(
    MxTargetNotCnameZoneValidator('mx-target-not-cname', sets={'strict'})
)
zone_validators.register(
    SrvTargetNotCnameZoneValidator('srv-target-not-cname', sets={'strict'})
)
zone_validators.register(
    ApexNsPresenceZoneValidator('apex-ns-presence', sets={'strict'})
)
zone_validators.register(
    MultiValueApexNsZoneValidator('multi-value-apex-ns', sets={'best-practice'})
)
zone_validators.register(
    OverlappingSubzoneZoneValidator(
        'overlapping-subzone', sets={'best-practice'}
    )
)
zone_validators.register(
    ApexCaaPresenceZoneValidator('apex-caa-presence', sets={'best-practice'})
)
zone_validators.register(
    MxTargetResolvableInZoneZoneValidator(
        'mx-target-resolvable-in-zone', sets={'best-practice'}
    )
)
zone_validators.register(
    SrvTargetResolvableInZoneZoneValidator(
        'srv-target-resolvable-in-zone', sets={'best-practice'}
    )
)
