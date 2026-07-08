#
#
#

from .base import Zone
from .validator import ValidationReason, ZoneValidator


class CaaZoneValidator(ZoneValidator):
    """
    Comprehensive best-practice validator for CAA records.

    Checks:

    1. **Presence of ``issue`` or ``issuewild``** — At least one CAA record
       must contain an ``issue`` or ``issuewild`` tag to explicitly authorize
       which Certificate Authorities may issue certificates.

    2. **Explicit wildcard policy** — If an ``issue`` tag is present but no
       ``issuewild`` tag exists, wildcard certificate issuance falls back to
       the ``issue`` policy. This validator recommends adding an explicit
       ``issuewild`` record to make the wildcard-issuance policy clear.

    Can operate in two modes: 'optional' (default) and 'required'. In 'optional'
    mode, the validator only runs if CAA records are present. In 'required'
    mode, a CAA record MUST be present at the zone apex.

    Regardless of mode, if CAA records are found (at the apex or at sub-domains)
    they will be validated against best practices.

    Enabled as part of the ``best-practice`` validator set::

      manager:
        enabled:
          - best-practice

    Examples:

    Common configuration for Let's Encrypt::

      - flags: 0
        tag: issue
        value: letsencrypt.org
      - flags: 0
        tag: issuewild
        value: letsencrypt.org

    Configuration for non-issuance (restricting all issuance)::

      - flags: 0
        tag: issue
        value: ";"

    References:

    - https://datatracker.ietf.org/doc/html/rfc8659
    - https://datatracker.ietf.org/doc/html/rfc9495
    """

    def __init__(self, id, presence='optional', sets=None):
        super().__init__(id, sets=sets)
        if presence not in ('optional', 'required'):
            raise ValueError(f'Unknown presence "{presence}"')
        self.presence = presence

    def validate(self, zone):
        reasons = []

        apex_caa = zone.get_type('', 'CAA')
        if not apex_caa and self.presence == 'required':
            reasons.append(
                ValidationReason(
                    f'zone "{zone.decoded_name}" has no CAA records at the apex',
                    set(),
                    validator_id=self.id,
                )
            )

        # Collect all CAA records in the zone.
        caa_records = [r for r in zone.records if r._type == 'CAA']

        for record in caa_records:
            # Collect all tags from all record values.
            tags = {value.tag for value in record.values}

            has_issue = 'issue' in tags
            has_issuewild = 'issuewild' in tags

            # Check 1: must have at least one issuance policy
            if not has_issue and not has_issuewild:
                reasons.append(
                    ValidationReason(
                        f'CAA record "{record.fqdn}" has no ``issue`` or ``issuewild`` tag; having only ``iodef`` means any CA can issue certificates',
                        [record],
                        validator_id=self.id,
                    )
                )

            # Check 2: if issue exists without issuewild, recommend explicit
            # wildcard policy
            if has_issue and not has_issuewild:
                reasons.append(
                    ValidationReason(
                        f'CAA record "{record.fqdn}" has ``issue`` but no ``issuewild``; consider adding an explicit ``issuewild`` to define wildcard certificate policy',
                        [record],
                        validator_id=self.id,
                    )
                )

        return reasons


Zone.register_zone_validator(
    CaaZoneValidator('caa-best-practices', sets={'best-practice'})
)
