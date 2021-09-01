#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from .base import BaseProcessor


class TypeAllowlistFilter(BaseProcessor):

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
