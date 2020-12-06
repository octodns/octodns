#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from ..zone import Zone


class BaseProcessor(object):

    def __init__(self, name):
        self.name = name

    def _create_zone(self, zone):
        return Zone(zone.name, sub_zones=zone.sub_zones)

    def process_source_zone(self, zone, sources):
        # sources may be empty, as will be the case for aliased zones
        return zone

    def process_target_zone(self, zone, target):
        return zone

    def process_plan(self, plan, sources, target):
        # plan may be None if no changes were detected up until now, the
        # process may still create a plan.
        # sources may be empty, as will be the case for aliased zones
        return plan
