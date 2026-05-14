#
#
#

from .base import Zone
from .validator import ValidationReason, ZoneValidator


class ApexCaaPresenceZoneValidator(ZoneValidator):
    """
    Comprehensive best-practice validator for CAA records at the zone apex.

    Checks:

    1. **Presence of ``issue`` or ``issuewild``** — At least one CAA record
       must contain an ``issue`` or ``issuewild`` tag to explicitly authorize
       which Certificate Authorities may issue certificates. Having only
       ``iodef`` (incident reporting) without any issuance policy means *any*
       CA can issue certificates for the domain.

    2. **Explicit wildcard policy** — If an ``issue`` tag is present but no
       ``issuewild`` tag exists, wildcard certificate issuance falls back to
       the ``issue`` policy. This validator recommends adding an explicit
       ``issuewild`` record to make the wildcard-issuance policy clear.

    3. **Incident reporting (``iodef``) recommendation** — Best practice
       suggests including an ``iodef`` tag so CAs can report abnormal or
       unauthorized certificate issuance attempts.

    Enabled as part of the ``best-practice`` validator set::

      manager:
        enabled:
          - best-practice

    References:

    - https://datatracker.ietf.org/doc/html/rfc8659
    - https://datatracker.ietf.org/doc/html/rfc9495
    """

    def validate(self, zone):
        reasons = []

        apex_records = zone.get('', type='CAA')
        if not apex_records:
            reasons.append(
                ValidationReason(
                    f'zone "{zone.decoded_name}" has no CAA records at the '
                    'apex',
                    set(),
                )
            )
            return reasons

        # Collect all tags from all apex CAA record values.
        tags = set()
        for record in apex_records:
            for value in record.values:
                tags.add(value.tag)

        has_issue = 'issue' in tags
        has_issuewild = 'issuewild' in tags
        has_iodef = 'iodef' in tags

        # Check 1: must have at least one issuance policy
        if not has_issue and not has_issuewild:
            reasons.append(
                ValidationReason(
                    f'zone "{zone.decoded_name}" CAA apex has no ``issue`` '
                    'or ``issuewild`` record; having only ``iodef`` means any '
                    'CA can issue certificates',
                    apex_records,
                )
            )

        # Check 2: if issue exists without issuewild, recommend explicit
        # wildcard policy
        if has_issue and not has_issuewild:
            reasons.append(
                ValidationReason(
                    f'zone "{zone.decoded_name}" CAA apex has ``issue`` but '
                    'no ``issuewild``; consider adding an explicit '
                    '``issuewild`` to define wildcard certificate policy',
                    apex_records,
                )
            )

        # Check 3: recommend iodef for incident reporting
        if not has_iodef:
            reasons.append(
                ValidationReason(
                    f'zone "{zone.decoded_name}" CAA apex has no ``iodef`` '
                    'record; consider adding one so CAs can report abnormal or '
                    'unauthorized issuance',
                    apex_records,
                )
            )

        return reasons


Zone.register_zone_validator(
    ApexCaaPresenceZoneValidator('apex-caa-presence', sets={'best-practice'})
)
