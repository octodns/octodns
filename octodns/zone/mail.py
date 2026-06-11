#
#
#

from logging import getLogger
from re import compile as re_compile
from re import error as re_error

from .base import Zone
from .validator import ValidationReason, ZoneValidator


class MailZoneValidator(ZoneValidator):
    '''
    Comprehensive best-practice validator for mail records (MX, SPF, DMARC).

    Can operate in two modes: 'mail' and 'no-mail'. In 'auto' mode (default),
    it detects the apex mode based on the presence of an apex MX record or an
    apex SPF record. If neither is present, it is a no-op for the apex (a lone
    DMARC record is not treated as a mail-mode signal). Mode is determined
    MX-first: if an apex MX record exists, Null MX (0 .) means 'no-mail',
    any other MX means 'mail'. If there is no apex MX, strict SPF
    'v=spf1 -all' at the apex means 'no-mail'; any other SPF means 'mail'.
    DMARC policy (p=) is never used for mode detection because p=reject is
    the recommended best practice for domains that DO send mail (RFC 7489)
    and therefore cannot discriminate between mail and no-mail zones.

    Every non-apex sub-domain that has MX records is also validated (redundancy
    + SPF). In 'auto' mode each sub-domain's mode is detected independently:
    null MX → 'no-mail', otherwise → 'mail'. In explicit 'mail' or 'no-mail'
    mode, the configured mode propagates to sub-domains.

    'mail' mode enforces:

    - At least ``min_mx`` MX records for redundancy (default 2) at the apex
      and throughout the zone. MX records with a single value whose exchange
      matches a known single-MX provider (see ``DEFAULT_SINGLE_MX_REGEXES``)
      or a user-supplied ``single_mx_regexes`` pattern are exempt from this
      check.
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

    # MX exchanges of providers known to (correctly) operate with a single MX
    # record. A record with exactly one value whose exchange matches one of
    # these patterns is exempt from the ``min_mx`` redundancy check. Patterns
    # are matched via re.search against the exchange including its trailing dot.
    #
    # PRs welcome: if you run across another reputable provider that only hands
    # out a single MX, please add it here.
    DEFAULT_SINGLE_MX_REGEXES = (
        r'^(feedback|inbound)-smtp\..+\.amazon(aws|ses)\.com\.$',  # Amazon AWS (region-specific)
        r'^inbound\.postmarkapp\.com\.$',  # Postmark
        r'^mx\.hubapi\.com\.$',  # HubSpot
        r'^mx\.sendgrid\.net\.$',  # SendGrid
        r'^smtp\.google\.com\.$',  # Google
        r'^smtp\.siftrock\.com.',  # Marketo
    )

    def __init__(
        self, id, mode='auto', min_mx=2, single_mx_regexes=None, sets=None
    ):
        super().__init__(id, sets=sets)
        self.log = getLogger(f'MailZoneValidator[{id}]')
        if mode not in ('auto', 'mail', 'no-mail'):
            raise ValueError(f'Unknown mode "{mode}"')
        self.mode = mode
        self.min_mx = min_mx
        self._single_mx_res = []
        # use set to get a unique list of regexes
        for r in set(
            (*self.DEFAULT_SINGLE_MX_REGEXES, *(single_mx_regexes or []))
        ):
            try:
                self._single_mx_res.append(re_compile(r))
            except re_error as e:
                raise ValueError(
                    f'Invalid single_mx_regexes pattern "{r}": {e}'
                )

    def _is_single_mx_provider(self, mx_record):
        # called only when mx_record has exactly one value
        exchange = str(mx_record.values[0].exchange)
        return any(r.search(exchange) for r in self._single_mx_res)

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

    def _parse_dmarc_tags(self, dmarc_value):
        if not dmarc_value:
            return {}
        tags = {}
        for part in dmarc_value.split(';'):
            part = part.strip()
            if not part:
                continue
            if '=' in part:
                tag, val = part.split('=', 1)
                tags[tag.strip().lower()] = val.strip().lower()
            else:
                tags[part.strip().lower()] = ''
        return tags

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
        else:
            dmarc_tags = self._parse_dmarc_tags(dmarc_value)
            if 'p' not in dmarc_tags:
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
        else:
            dmarc_tags = self._parse_dmarc_tags(dmarc_value)
            if dmarc_tags.get('p') != 'reject':
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

            if len(record.values) < self.min_mx:
                # only a lone MX can belong to an exempt single-MX provider;
                # skip the regex matching when it couldn't help
                if len(record.values) == 1 and self._is_single_mx_provider(
                    record
                ):
                    continue
                reasons.append(
                    ValidationReason(
                        f'MX record "{record.fqdn}" should have at least {self.min_mx} values for redundancy, found {len(record.values)}',
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
            # Update mode to mail/no-mail based on detection.
            # MX is the primary signal; SPF is the fallback. DMARC policy is
            # never used for detection: p=reject is the recommended practice
            # for domains that DO send mail and therefore cannot distinguish
            # mail from no-mail zones (issue #1422).
            if apex_mx_record or apex_spf_value:
                self.log.debug(
                    'validate: zone=%s, has mail related records/values, apex_mx_record=%s, apex_spf_value=%s, dmarc_value=%s',
                    zone.decoded_name,
                    apex_mx_record,
                    apex_spf_value,
                    dmarc_value,
                )
                if apex_mx_record:
                    if self._is_null_mx(apex_mx_record):
                        self.log.debug(
                            'validate: zone=%s, apex_mx_record (Null MX) indicates no-mail',
                            zone.decoded_name,
                        )
                        mode = 'no-mail'
                    else:
                        self.log.debug(
                            'validate: zone=%s, apex_mx_record indicates mail handling',
                            zone.decoded_name,
                        )
                        mode = 'mail'
                elif apex_spf_value == 'v=spf1 -all':
                    self.log.debug(
                        'validate: zone=%s, apex_spf_value indicates no-mail',
                        zone.decoded_name,
                    )
                    mode = 'no-mail'
                else:
                    self.log.debug(
                        'validate: zone=%s, apex_spf_value indicates mail handling',
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


class MxTargetResolvableInZoneZoneValidator(ZoneValidator):
    '''
    Checks that ``MX`` exchanges pointing to targets within the same zone have
    corresponding address records.
    '''

    def validate(self, zone):
        reasons = []
        for record in zone.records:
            if record._type == 'MX':
                for value in record.values:
                    target = value.exchange
                    if zone.owns('A', target):
                        hostname = zone.hostname_from_fqdn(target)
                        if not zone.get(hostname):
                            reasons.append(
                                ValidationReason(
                                    f'MX record "{record.decoded_fqdn}" points to in-zone target "{target}" that does not exist',
                                    [record],
                                )
                            )
        return reasons


Zone.register_zone_validator(
    MxTargetResolvableInZoneZoneValidator(
        'mx-target-resolvable-in-zone', sets={'best-practice'}
    )
)
