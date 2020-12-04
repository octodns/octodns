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

    def process(self, zone, target=False):
        ret = self._create_zone(zone)
        for record in zone.records:
            if record._type in self.allowlist:
                ret.add_record(record)

        return ret


class TypeRejectlistFilter(BaseProcessor):

    def __init__(self, name, rejectlist):
        super(TypeRejectlistFilter, self).__init__(name)
        self.rejectlist = rejectlist

    def process(self, zone, target=False):
        ret = self._create_zone(zone)
        for record in zone.records:
            if record._type not in self.rejectlist:
                ret.add_record(record)

        return ret
