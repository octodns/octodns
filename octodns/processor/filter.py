#
#
#

from re import compile as re_compile

from ..record.exception import ValidationError
from .base import BaseProcessor


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


class _TypeBaseFilter(BaseProcessor):
    def __init__(self, name, _list):
        super().__init__(name)
        self._list = set(_list)

    def _process(self, zone, *args, **kwargs):
        for record in zone.records:
            if record._type in self._list:
                self.matches(zone, record)
            else:
                self.doesnt_match(zone, record)

        return zone

    process_source_zone = _process
    process_target_zone = _process


class TypeAllowlistFilter(_TypeBaseFilter, AllowsMixin):
    '''Only manage records of the specified type(s).

    Example usage:

    processors:
      only-a-and-aaaa:
        class: octodns.processor.filter.TypeAllowlistFilter
        allowlist:
          - A
          - AAAA

    zones:
      exxampled.com.:
        sources:
          - config
        processors:
          - only-a-and-aaaa
        targets:
          - ns1
    '''

    def __init__(self, name, allowlist):
        super().__init__(name, allowlist)


class TypeRejectlistFilter(_TypeBaseFilter, RejectsMixin):
    '''Ignore records of the specified type(s).

    Example usage:

    processors:
      ignore-cnames:
        class: octodns.processor.filter.TypeRejectlistFilter
        rejectlist:
          - CNAME

    zones:
      exxampled.com.:
        sources:
          - config
        processors:
          - ignore-cnames
        targets:
          - route53
    '''

    def __init__(self, name, rejectlist):
        super().__init__(name, rejectlist)


class _NameBaseFilter(BaseProcessor):
    def __init__(self, name, _list):
        super().__init__(name)
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

    process_source_zone = _process
    process_target_zone = _process


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


class ZoneNameFilter(BaseProcessor):
    '''Filter or error on record names that contain the zone name

    Example usage:

    processors:
      zone-name:
        class: octodns.processor.filter.ZoneNameFilter
        # If true a ValidationError will be throw when such records are
        # encouterd, if false the records will just be ignored/omitted.
        # (default: false)

    zones:
      exxampled.com.:
        sources:
          - config
        processors:
          - zone-name
        targets:
          - azure
    '''

    def __init__(self, name, error=False):
        super().__init__(name)
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

    process_source_zone = _process
    process_target_zone = _process
