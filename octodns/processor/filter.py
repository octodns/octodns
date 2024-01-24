#
#
#

from ipaddress import ip_address, ip_network
from itertools import product
from logging import getLogger
from re import compile as re_compile

from ..record.exception import ValidationError
from .base import BaseProcessor


class _FilterProcessor(BaseProcessor):
    def __init__(self, name, include_target=True, **kwargs):
        super().__init__(name, **kwargs)
        self.include_target = include_target

    def process_source_zone(self, *args, **kwargs):
        return self._process(*args, **kwargs)

    def process_target_zone(self, existing, *args, **kwargs):
        if self.include_target:
            return self._process(existing, *args, **kwargs)
        return existing


class AllowsMixin:
    def matches(self, zone, record):
        pass

    def doesnt_match(self, zone, record):
        zone.remove_record(record)


class RejectsMixin:
    def matches(self, zone, record):
        zone.remove_record(record)

    def doesnt_match(self, zone, record):
        pass


class _TypeBaseFilter(_FilterProcessor):
    def __init__(self, name, _list, **kwargs):
        super().__init__(name, **kwargs)
        self._list = set(_list)

    def _process(self, zone, *args, **kwargs):
        for record in zone.records:
            if record._type in self._list:
                self.matches(zone, record)
            else:
                self.doesnt_match(zone, record)

        return zone


class TypeAllowlistFilter(_TypeBaseFilter, AllowsMixin):
    '''Only manage records of the specified type(s).

    Example usage:

    processors:
      only-a-and-aaaa:
        class: octodns.processor.filter.TypeAllowlistFilter
        allowlist:
          - A
          - AAAA
        # Optional param that can be set to False to leave the target zone
        # alone, thus allowing deletion of existing records
        # (default: true)
        # include_target: True

    zones:
      exxampled.com.:
        sources:
          - config
        processors:
          - only-a-and-aaaa
        targets:
          - ns1
    '''

    def __init__(self, name, allowlist, **kwargs):
        super().__init__(name, allowlist, **kwargs)


class TypeRejectlistFilter(_TypeBaseFilter, RejectsMixin):
    '''Ignore records of the specified type(s).

    Example usage:

    processors:
      ignore-cnames:
        class: octodns.processor.filter.TypeRejectlistFilter
        rejectlist:
          - CNAME
        # Optional param that can be set to False to leave the target zone
        # alone, thus allowing deletion of existing records
        # (default: true)
        # include_target: True

    zones:
      exxampled.com.:
        sources:
          - config
        processors:
          - ignore-cnames
        targets:
          - route53
    '''

    def __init__(self, name, rejectlist, **kwargs):
        super().__init__(name, rejectlist, **kwargs)


class _NameBaseFilter(_FilterProcessor):
    def __init__(self, name, _list, **kwargs):
        super().__init__(name, **kwargs)
        exact = set()
        regex = []
        for pattern in _list:
            if pattern.startswith('/'):
                regex.append(re_compile(pattern[1:-1]))
            else:
                exact.add(pattern)
        self.exact = exact
        self.regex = regex

    def _process(self, zone, *args, **kwargs):
        for record in zone.records:
            name = record.name
            if name in self.exact:
                self.matches(zone, record)
                continue
            elif any(r.search(name) for r in self.regex):
                self.matches(zone, record)
                continue

            self.doesnt_match(zone, record)

        return zone


class NameAllowlistFilter(_NameBaseFilter, AllowsMixin):
    '''Only manage records with names that match the provider patterns

    Example usage:

    processors:
      only-these:
        class: octodns.processor.filter.NameAllowlistFilter
        allowlist:
          # exact string match
          - www
          # contains/substring match
          - /substring/
          # regex pattern match
          - /some-pattern-\\d\\+/
          # regex - anchored so has to match start to end
          - /^start-.+-end$/
        # Optional param that can be set to False to leave the target zone
        # alone, thus allowing deletion of existing records
        # (default: true)
        # include_target: True

    zones:
      exxampled.com.:
        sources:
          - config
        processors:
          - only-these
        targets:
          - route53
    '''

    def __init__(self, name, allowlist):
        super().__init__(name, allowlist)


class NameRejectlistFilter(_NameBaseFilter, RejectsMixin):
    '''Reject managing records with names that match the provider patterns

    Example usage:

    processors:
      not-these:
        class: octodns.processor.filter.NameRejectlistFilter
        rejectlist:
          # exact string match
          - www
          # contains/substring match
          - /substring/
          # regex pattern match
          - /some-pattern-\\d\\+/
          # regex - anchored so has to match start to end
          - /^start-.+-end$/
        # Optional param that can be set to False to leave the target zone
        # alone, thus allowing deletion of existing records
        # (default: true)
        # include_target: True

    zones:
      exxampled.com.:
        sources:
          - config
        processors:
          - not-these
        targets:
          - route53
    '''

    def __init__(self, name, rejectlist):
        super().__init__(name, rejectlist)


class _ValueBaseFilter(_FilterProcessor):
    def __init__(self, name, _list, **kwargs):
        super().__init__(name, **kwargs)
        exact = set()
        regex = []
        for pattern in _list:
            if pattern.startswith('/'):
                regex.append(re_compile(pattern[1:-1]))
            else:
                exact.add(pattern)
        self.exact = exact
        self.regex = regex

    def _process(self, zone, *args, **kwargs):
        for record in zone.records:
            values = []
            if hasattr(record, 'values'):
                values = [value.rdata_text for value in record.values]
            else:
                values = [record.value.rdata_text]

            if any(value in self.exact for value in values):
                self.matches(zone, record)
                continue
            elif any(r.search(value) for r in self.regex for value in values):
                self.matches(zone, record)
                continue

            self.doesnt_match(zone, record)

        return zone


class ValueAllowlistFilter(_ValueBaseFilter, AllowsMixin):
    '''Only manage records with values that match the provider patterns

    Example usage:

    processors:
      only-these:
        class: octodns.processor.filter.ValueAllowlistFilter
        allowlist:
          # exact string match
          - www
          # contains/substring match
          - /substring/
          # regex pattern match
          - /some-pattern-\\d\\+/
          # regex - anchored so has to match start to end
          - /^start-.+-end$/
        # Optional param that can be set to False to leave the target zone
        # alone, thus allowing deletion of existing records
        # (default: true)
        # include_target: True

    zones:
      exxampled.com.:
        sources:
          - config
        processors:
          - only-these
        targets:
          - route53
    '''

    def __init__(self, name, allowlist):
        super().__init__(name, allowlist)


class ValueRejectlistFilter(_ValueBaseFilter, RejectsMixin):
    '''Reject managing records with names that match the provider patterns

    Example usage:

    processors:
      not-these:
        class: octodns.processor.filter.ValueRejectlistFilter
        rejectlist:
          # exact string match
          - www
          # contains/substring match
          - /substring/
          # regex pattern match
          - /some-pattern-\\d\\+/
          # regex - anchored so has to match start to end
          - /^start-.+-end$/
        # Optional param that can be set to False to leave the target zone
        # alone, thus allowing deletion of existing records
        # (default: true)
        # include_target: True

    zones:
      exxampled.com.:
        sources:
          - config
        processors:
          - not-these
        targets:
          - route53
    '''

    def __init__(self, name, rejectlist):
        super().__init__(name, rejectlist)


class _NetworkValueBaseFilter(BaseProcessor):
    def __init__(self, name, _list):
        super().__init__(name)
        self.networks = []
        for value in _list:
            try:
                self.networks.append(ip_network(value))
            except ValueError:
                raise ValueError(f'{value} is not a valid CIDR to use')

    def _process(self, zone, *args, **kwargs):
        for record in zone.records:
            if record._type not in ['A', 'AAAA']:
                continue

            ips = [ip_address(value) for value in record.values]
            if any(
                ip in network for ip, network in product(ips, self.networks)
            ):
                self.matches(zone, record)
            else:
                self.doesnt_match(zone, record)

        return zone

    process_source_zone = _process
    process_target_zone = _process


class NetworkValueAllowlistFilter(_NetworkValueBaseFilter, AllowsMixin):
    '''Only manage A and AAAA records with values that match the provider patterns
    All other types will be left as-is.

    Example usage:

    processors:
      only-these:
        class: octodns.processor.filter.NetworkValueAllowlistFilter
        allowlist:
          - 127.0.0.1/32
          - 192.168.0.0/16
          - fd00::/8

    zones:
      exxampled.com.:
        sources:
          - config
        processors:
          - only-these
        targets:
          - route53
    '''

    def __init__(self, name, allowlist):
        super().__init__(name, allowlist)


class NetworkValueRejectlistFilter(_NetworkValueBaseFilter, RejectsMixin):
    '''Reject managing A and AAAA records with value matching a that match the provider patterns
    All other types will be left as-is.

    Example usage:

    processors:
      not-these:
        class: octodns.processor.filter.NetworkValueRejectlistFilter
        rejectlist:
          - 127.0.0.1/32
          - 192.168.0.0/16
          - fd00::/8

    zones:
      exxampled.com.:
        sources:
          - config
        processors:
          - not-these
        targets:
          - route53
    '''

    def __init__(self, name, rejectlist):
        super().__init__(name, rejectlist)


class IgnoreRootNsFilter(BaseProcessor):
    '''Do not manage Root NS Records.

    Example usage:

    processors:
      no-root-ns:
        class: octodns.processor.filter.IgnoreRootNsFilter

    zones:
      exxampled.com.:
        sources:
          - config
        processors:
          - no-root-ns
        targets:
          - ns1
    '''

    def _process(self, zone, *args, **kwargs):
        for record in zone.records:
            if record._type == 'NS' and not record.name:
                zone.remove_record(record)

        return zone

    process_source_zone = _process
    process_target_zone = _process


class ExcludeRootNsChanges(BaseProcessor):
    '''Do not allow root NS record changes

    Example usage:

    processors:
      exclude-root-ns-changes:
        class: octodns.processor.filter.ExcludeRootNsChanges
        # If true an a change for a root NS is seen an error will be thrown. If
        # false a warning will be printed and the change will be removed from
        # the plan.
        # (default: true)
        error: true

    zones:
      exxampled.com.:
        sources:
          - config
        processors:
          - exclude-root-ns-changes
        targets:
          - ns1
    '''

    def __init__(self, name, error=True):
        self.log = getLogger(f'ExcludeRootNsChanges[{name}]')
        super().__init__(name)
        self.error = error

    def process_plan(self, plan, sources, target):
        if plan:
            for change in list(plan.changes):
                record = change.record
                if record._type == 'NS' and record.name == '':
                    self.log.warning(
                        'root NS changes are disallowed, fqdn=%s', record.fqdn
                    )
                    if self.error:
                        raise ValidationError(
                            record.fqdn,
                            ['root NS changes are disallowed'],
                            record.context,
                        )
                    plan.changes.remove(change)

            print(len(plan.changes))

        return plan


class ZoneNameFilter(_FilterProcessor):
    '''Filter or error on record names that contain the zone name

    Example usage:

    processors:
      zone-name:
        class: octodns.processor.filter.ZoneNameFilter
        # If true a ValidationError will be throw when such records are
        # encouterd, if false the records will just be ignored/omitted.
        # (default: true)
        # Optional param that can be set to False to leave the target zone
        # alone, thus allowing deletion of existing records
        # (default: true)
        # include_target: True

    zones:
      exxampled.com.:
        sources:
          - config
        processors:
          - zone-name
        targets:
          - azure
    '''

    def __init__(self, name, error=True, **kwargs):
        super().__init__(name, **kwargs)
        self.error = error

    def _process(self, zone, *args, **kwargs):
        zone_name_with_dot = zone.name
        zone_name_without_dot = zone_name_with_dot[:-1]
        for record in zone.records:
            name = record.name
            if name.endswith(zone_name_with_dot) or name.endswith(
                zone_name_without_dot
            ):
                if self.error:
                    raise ValidationError(
                        record.fqdn,
                        ['record name ends with zone name'],
                        record.context,
                    )
                else:
                    # just remove it
                    zone.remove_record(record)

        return zone
