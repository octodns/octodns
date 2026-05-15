#
#
#

from logging import getLogger

from .base import Zone
from .validator import ValidationReason, ZoneValidator


class MailZoneValidator(ZoneValidator):
    '''
    Comprehensive best-practice validator for mail records (MX, SPF, DMARC).

    Can operate in two modes: 'mail' and 'no-mail'. In 'auto' mode (default),
    it detects the apex mode based on the presence of mail-related records (MX
    anywhere in the zone, SPF at the apex, or DMARC at _dmarc). If no
    mail-related records are found, it is a no-op for the apex. If any are
    found, it detects the mode based on the presence of non-null MX records at
    the apex.

    Every non-apex sub-domain that has MX records is also validated (redundancy
    + SPF). In 'auto' mode each sub-domain's mode is detected independently:
    null MX → 'no-mail', otherwise → 'mail'. In explicit 'mail' or 'no-mail'
    mode, the configured mode propagates to sub-domains.

    'mail' mode enforces:
    - Multiple MX records for redundancy (at apex and throughout the zone).
    - Presence of an SPF record at the apex.
    - SPF record terminates with ~all or -all.
    - Presence of a DMARC record at _dmarc.
    - Each sub-domain with MX has an SPF record terminating with ~all or -all.

    'no-mail' mode enforces:
    - Presence of a single Null MX record (0 .) at the apex.
    - SPF record at the apex is exactly 'v=spf1 -all'.
    - DMARC record at _dmarc has p=reject.
    - Each sub-domain with MX has a single Null MX (0 .) and strict SPF
      'v=spf1 -all'.

    DMARC is not required at the sub-domain level because it inherits from the
    parent zone per RFC 7489 §6.6.3.
    '''

    def __init__(self, id, mode='auto', sets=None):
        super().__init__(id, sets=sets)
        self.log = getLogger(f'MailZoneValidator[{id}]')
        if mode not in ('auto', 'mail', 'no-mail'):
            raise ValueError(f'Unknown mode "{mode}"')
        self.mode = mode

    def _is_null_mx(self, mx_record):
        return (
            len(mx_record.values) == 1
            and mx_record.values[0].preference == 0
            and str(mx_record.values[0].exchange) == '.'
        )

    def _extract_spf(self, txt_record, multi_msg):
        if txt_record is None:
            return None, None
        values = [
            v
            for v in (i.lower().replace('\\', '') for i in txt_record.values)
            if v.startswith('v=spf1')
        ]
        if not values:
            return None, None
        reason = None
        if len(values) > 1:
            reason = ValidationReason(reason=multi_msg, records={txt_record})
        return values[0], reason

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
        elif not self._is_null_mx(apex_mx_record):
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

    def _detect_subdomain_mode(self, mx_record):
        if self._is_null_mx(mx_record):
            return 'no-mail'
        return 'mail'

    def _validate_subdomain(self, zone, mx_record, mode):
        reasons = []
        txt_record = zone.get_type(mx_record.name, 'TXT')

        spf_value, spf_multi = self._extract_spf(
            txt_record, f'"{mx_record.decoded_fqdn}" has multiple SPF values'
        )
        if spf_multi:
            reasons.append(spf_multi)

        records = {mx_record}
        if txt_record:
            records.add(txt_record)

        if mode == 'mail':
            if not spf_value:
                reasons.append(
                    ValidationReason(
                        f'"{mx_record.decoded_fqdn}" handles mail but is missing an SPF TXT record',
                        records,
                    )
                )
            elif not (
                spf_value.endswith(' -all') or spf_value.endswith(' ~all')
            ):
                reasons.append(
                    ValidationReason(
                        f'SPF record at "{mx_record.decoded_fqdn}" should terminate with "~all" or "-all"',
                        {txt_record},
                    )
                )
        else:
            if not self._is_null_mx(mx_record):
                reasons.append(
                    ValidationReason(
                        f'"{mx_record.decoded_fqdn}" disables mail and should have a single Null MX record (0 .)',
                        {mx_record},
                    )
                )
            if spf_value is None:
                reasons.append(
                    ValidationReason(
                        f'"{mx_record.decoded_fqdn}" disables mail but is missing strict SPF TXT record "v=spf1 -all"',
                        records,
                    )
                )
            elif spf_value != 'v=spf1 -all':
                reasons.append(
                    ValidationReason(
                        f'"{mx_record.decoded_fqdn}" disables mail and should have a strict SPF TXT record "v=spf1 -all"',
                        {txt_record},
                    )
                )

        return reasons

    def validate(self, zone):
        reasons = []

        mode = self.mode

        non_apex_mx = [
            r for r in zone.records if r.name != '' and r._type == 'MX'
        ]

        apex_mx_record = zone.get_type('', 'MX')

        # MX redundancy (Apex and elsewhere)
        for record in (
            [apex_mx_record] if apex_mx_record else []
        ) + non_apex_mx:
            if self._is_null_mx(record):
                continue

            if len(record.values) < 2:
                reasons.append(
                    ValidationReason(
                        f'MX record "{record.fqdn}" should have at least 2 values for redundancy, found {len(record.values)}',
                        [record],
                    )
                )

        apex_txt = zone.get_type('', 'TXT')
        apex_spf_value, apex_spf_multi = self._extract_spf(
            apex_txt, f'zone "{zone.decoded_name}" has multiple SPF values'
        )
        if apex_spf_multi:
            reasons.append(apex_spf_multi)

        dmarc_txt = zone.get_type('_dmarc', 'TXT')
        dmarc_value = (
            [
                v
                for v in [v.lower().replace('\\', '') for v in dmarc_txt.values]
                if v.startswith('v=dmarc1')
            ]
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
                        'validate: zone=%s, apex_spf_value indicates no-mail',
                        zone.decoded_name,
                    )
                    mode = 'no-mail'
                elif dmarc_value and dmarc_value == 'v=dmarc1; p=reject;':
                    self.log.debug(
                        'validate: zone=%s, dmarc_value indicates no-mail',
                        zone.decoded_name,
                    )
                    mode = 'no-mail'
                elif apex_mx_record and self._is_null_mx(apex_mx_record):
                    self.log.debug(
                        'validate: zone=%s, apex_mx_record indicates no-mail',
                        zone.decoded_name,
                    )
                    mode = 'no-mail'
                else:
                    self.log.debug(
                        'validate: zone=%s, assuming mail handling',
                        zone.decoded_name,
                    )
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

        for mx_record in non_apex_mx:
            sub_mode = (
                self._detect_subdomain_mode(mx_record)
                if self.mode == 'auto'
                else self.mode
            )
            reasons.extend(self._validate_subdomain(zone, mx_record, sub_mode))

        return reasons


class MxTargetNotCnameZoneValidator(ZoneValidator):
    '''
    Checks that MX records do not point to exchanges that are CNAMEs within
    the same zone. Per RFC 2181 §10.3, the MX exchange must be an A/AAAA
    record, not a CNAME.
    '''

    def validate(self, zone):
        reasons = []
        for record in zone.records:
            if record._type == 'MX':
                for value in record.values:
                    target = value.exchange
                    if target == '.':
                        continue
                    if zone.owns('CNAME', target):
                        hostname = zone.hostname_from_fqdn(target)
                        cnames = zone.get(hostname, type='CNAME')
                        if cnames:
                            reasons.append(
                                ValidationReason(
                                    f'MX record "{record.fqdn}" points to exchange "{target}" which is a CNAME',
                                    [record],
                                )
                            )
        return reasons


Zone.register_zone_validator(
    MxTargetNotCnameZoneValidator('mx-target-not-cname', sets={'strict'})
)

Zone.register_zone_validator(MailZoneValidator('mail', sets={'best-practice'}))
