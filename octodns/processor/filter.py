#
#
#

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from .base import BaseProcessor


class TypeAllowlistFilter(BaseProcessor):
    '''Only manage records of the specified type(s).

    Example usage:

    processors:
      only-a-and-aaaa:
        class: octodns.processor.filter.TypeRejectlistFilter
        rejectlist:
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
        super(TypeAllowlistFilter, self).__init__(name)
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
        super(TypeRejectlistFilter, self).__init__(name)
        self.rejectlist = set(rejectlist)

    def _process(self, zone, *args, **kwargs):
        for record in zone.records:
            if record._type in self.rejectlist:
                zone.remove_record(record)

        return zone

    process_source_zone = _process
    process_target_zone = _process
