#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from . import BaseProcessor


class TypeAllowlistFilter(BaseProcessor):

    def __init__(self, name, allowlist):
        super(TypeAllowlistFilter, self).__init__(name)
        self.allowlist = allowlist

    def _process(self, zone, *args, **kwargs):
        ret = self._clone_zone(zone)
        for record in zone.records:
            if record._type in self.allowlist:
                ret.add_record(record)

        return ret

    process_source_zone = _process
    process_target_zone = _process


class TypeRejectlistFilter(BaseProcessor):

    def __init__(self, name, rejectlist):
        super(TypeRejectlistFilter, self).__init__(name)
        self.rejectlist = rejectlist

    def _process(self, zone, *args, **kwargs):
        ret = self._clone_zone(zone)
        for record in zone.records:
            if record._type not in self.rejectlist:
                ret.add_record(record)

        return ret

    process_source_zone = _process
    process_target_zone = _process
