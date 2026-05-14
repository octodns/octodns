#
#
#

from logging import getLogger

from .base import Zone
from .validator import ValidationReason, ZoneValidator


class MailZoneValidator(ZoneValidator):
    '''
    Comprehensive best-practice validator for mail records (MX, SPF, DMARC).

    Can operate in two modes: 'mail' and 'no-mail'. In 'auto' mode (default), it
    detects the mode based on the presence of mail-related records (MX anywhere
    in the zone, SPF at the apex, or DMARC at _dmarc). If no mail-related
    records are found, it is a no-op. If any are found, it detects the mode
    based on the presence of non-null MX records at the apex.

    'mail' mode enforces:
    - Multiple MX records for redundancy (at apex and throughout the zone).
    - Presence of an SPF record at the apex.
    - SPF record terminates with ~all or -all.
    - Presence of a DMARC record at _dmarc.

    'no-mail' mode enforces:
    - Presence of a single Null MX record (0 .) at the apex.
    - SPF record at the apex is exactly 'v=spf1 -all'.
    - DMARC record at _dmarc has p=reject.
    '''

    def __init__(self, id, mode='auto', sets=None):
        super().__init__(id, sets=sets)
        self.log = getLogger(f'MailZoneValidator[{id}]')
        if mode not in ('auto', 'mail', 'no-mail'):
            raise ValueError(f'Unknown mode "{mode}"')
        self.mode = mode

    def _validate_mail(
        self,
        zone,
        apex_mx_record,
        apex_txt,
        apex_spf_value,
        dmarc_txt,
        dmarc_value,
    ):
        reasons = []

        records = set()
        if apex_mx_record:
            records.add(apex_mx_record)
        if apex_txt:
            records.add(apex_txt)
        if dmarc_txt:
            records.add(dmarc_txt)

        # Check for presence at apex
        if not apex_mx_record:
            reasons.append(
                ValidationReason(
                    f'zone "{zone.decoded_name}" handles mail but is missing MX records at the apex',
                    records,
                )
            )

        # SPF
        if not apex_spf_value:
            reasons.append(
                ValidationReason(
                    f'zone "{zone.decoded_name}" handles mail but is missing an SPF TXT record at the apex',
                    records,
                )
            )
        elif not (
            apex_spf_value.endswith(' -all') or apex_spf_value.endswith(' ~all')
        ):
            reasons.append(
                ValidationReason(
                    f'SPF record at the apex of "{zone.decoded_name}" should terminate with "~all" or "-all"',
                    {apex_txt},
                )
            )

        # DMARC
        if not dmarc_value:
            reasons.append(
                ValidationReason(
                    f'zone "{zone.decoded_name}" handles mail but is missing a DMARC TXT record at _dmarc',
                    records,
                )
            )
        elif 'p=' not in dmarc_value:
            reasons.append(
                ValidationReason(
                    f'DMARC record at _dmarc.{zone.decoded_name} is missing a policy (p=...)',
                    [dmarc_txt],
                )
            )

        return reasons

    def _validate_no_mail(
        self,
        zone,
        apex_mx_record,
        apex_txt,
        apex_spf_value,
        dmarc_txt,
        dmarc_value,
    ):
        reasons = []

        records = set()
        if apex_mx_record:
            records.add(apex_mx_record)
        if apex_txt:
            records.add(apex_txt)
        if dmarc_txt:
            records.add(dmarc_txt)

        # MX
        if not apex_mx_record:
            reasons.append(
                ValidationReason(
                    f'zone "{zone.decoded_name}" disables mail but is missing a Null MX record (0 .)',
                    records,
                )
            )
        elif (
            len(apex_mx_record.values) != 1
            or apex_mx_record.values[0].preference != 0
            or str(apex_mx_record.values[0].exchange) != '.'
        ):
            reasons.append(
                ValidationReason(
                    f'zone "{zone.decoded_name}" disables mail and should have a single Null MX record (0 .)',
                    [apex_mx_record],
                )
            )

        # SPF
        if apex_spf_value is None:
            reasons.append(
                ValidationReason(
                    f'zone "{zone.decoded_name}" disables mail but is missing strict SPF TXT record "v=spf1 -all"',
                    records,
                )
            )
        elif not apex_spf_value == 'v=spf1 -all':
            reasons.append(
                ValidationReason(
                    f'zone "{zone.decoded_name}" disables mail and should have a single strict SPF TXT record "v=spf1 -all"',
                    [apex_txt],
                )
            )

        # DMARC
        if dmarc_value is None:
            reasons.append(
                ValidationReason(
                    f'zone "{zone.decoded_name}" disables mail but is missing strict DMARC TXT record "v=DMARC1; p=reject;"',
                    records,
                )
            )
        elif 'p=reject' not in dmarc_value:
            reasons.append(
                ValidationReason(
                    f'zone "{zone.decoded_name}" disables mail and should have a DMARC TXT record with "v=DMARC1; p=reject;"',
                    [dmarc_txt],
                )
            )

        return reasons

    def validate(self, zone):
        reasons = []

        mode = self.mode

        apex_mx_record = zone.get_type('', 'MX')

        # MX redundancy (Apex and elsewhere)
        for record in ([apex_mx_record] if apex_mx_record else []) + [
            r for r in zone.records if r.name != '' and r._type == 'MX'
        ]:
            if len(record.values) < 2:
                reasons.append(
                    ValidationReason(
                        f'MX record "{record.fqdn}" should have at least 2 values for redundancy, found {len(record.values)}',
                        [record],
                    )
                )

        apex_txt = zone.get_type('', 'TXT')
        apex_spf_value = (
            [
                v
                for v in [i.lower().replace('\\', '') for i in apex_txt.values]
                if v.startswith('v=spf1')
            ]
            # there can only be 0/1
            if apex_txt
            else None
        )
        if apex_spf_value:
            if len(apex_spf_value) > 1:
                reasons.append(
                    ValidationReason(
                        reason=f'zone "{zone.decoded_name}" has multiple SPF values',
                        records={apex_txt},
                    )
                )
            apex_spf_value = apex_spf_value[0]

        dmarc_txt = zone.get_type('_dmarc', 'TXT')
        dmarc_value = (
            [
                v
                for v in [v.lower().replace('\\', '') for v in dmarc_txt.values]
                if v.startswith('v=dmarc1')
            ]
            # there can only be 0/1
            if dmarc_txt
            else None
        )
        if dmarc_value:
            if len(dmarc_value) > 1:
                reasons.append(
                    ValidationReason(
                        reason=f'zone "{zone.decoded_name}" has multiple DMARC values',
                        records={dmarc_txt},
                    )
                )
            dmarc_value = dmarc_value[0]

        if mode == 'auto':
            # update mode to main/no-mail based on detection
            if apex_mx_record or apex_spf_value or dmarc_value:
                self.log.debug(
                    'validate: zone=%s, has mail related records/values, apex_mx_record=%s, apex_spf_value=%s, dmarc_value=%s',
                    zone.decoded_name,
                    apex_mx_record,
                    apex_spf_value,
                    dmarc_value,
                )
                if apex_spf_value and apex_spf_value == 'v=spf1 -all':
                    self.log.debug(
                        'validate: zone=%s, apex_spf_value indicates no-mail'
                    )
                    mode = 'no-mail'
                elif dmarc_value and dmarc_value == 'v=dmarc1; p=reject;':
                    self.log.debug(
                        'validate: zone=%s, dmarc_value indicates no-mail'
                    )
                    mode = 'no-mail'
                elif (
                    apex_mx_record
                    and len(apex_mx_record.values) == 1
                    and apex_mx_record.values[0].preference == 0
                    and apex_mx_record.values[0].exchange == '.'
                ):
                    self.log.debug(
                        'validate: zone=%s, apex_mx_record indicates'
                    )
                    mode = 'no-mail'
                else:
                    self.log.debug('validate: zone=%s, assuming mail handling')
                    mode = 'mail'

        if mode == 'mail':
            reasons.extend(
                self._validate_mail(
                    zone,
                    apex_mx_record=apex_mx_record,
                    apex_txt=apex_txt,
                    apex_spf_value=apex_spf_value,
                    dmarc_txt=dmarc_txt,
                    dmarc_value=dmarc_value,
                )
            )
        elif mode == 'no-mail':
            reasons.extend(
                self._validate_no_mail(
                    zone,
                    apex_mx_record=apex_mx_record,
                    apex_txt=apex_txt,
                    apex_spf_value=apex_spf_value,
                    dmarc_txt=dmarc_txt,
                    dmarc_value=dmarc_value,
                )
            )

        return reasons


Zone.register_zone_validator(MailZoneValidator('mail', sets={'best-practice'}))
