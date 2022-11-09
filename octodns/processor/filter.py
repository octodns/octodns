#
#
#

from re import compile as re_compile

from .base import BaseProcessor


class TypeAllowlistFilter(BaseProcessor):
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
        super().__init__(name)
        self.allowlist = set(allowlist)

    def _process(self, zone, *args, **kwargs):
        for record in zone.records:
            if record._type not in self.allowlist:
                zone.remove_record(record)

        return zone

    process_source_zone = _process
    process_target_zone = _process


class TypeRejectlistFilter(BaseProcessor):
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
        super().__init__(name)
        self.rejectlist = set(rejectlist)

    def _process(self, zone, *args, **kwargs):
        for record in zone.records:
            if record._type in self.rejectlist:
                zone.remove_record(record)

        return zone

    process_source_zone = _process
    process_target_zone = _process


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


class NameAllowlistFilter(_NameBaseFilter):
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

    def _process(self, zone, *args, **kwargs):
        for record in zone.records:
            name = record.name
            if name in self.exact:
                continue
            elif any(r.search(name) for r in self.regex):
                continue

            zone.remove_record(record)

        return zone

    process_source_zone = _process
    process_target_zone = _process


class NameRejectlistFilter(_NameBaseFilter):
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

    def _process(self, zone, *args, **kwargs):
        for record in zone.records:
            name = record.name
            if name in self.exact:
                zone.remove_record(record)
                continue

            for regex in self.regex:
                if regex.search(name):
                    zone.remove_record(record)
                    break

        return zone

    process_source_zone = _process
    process_target_zone = _process


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
